#!/usr/bin/env python3
"""
OpenRouter cost/usage updater for the Omarchy top bar plugin `openrouter.cost`.

Aggregates cost across ALL configured OpenRouter API keys. Keys can share one
OpenRouter account, so account-level (lifetime / balance) figures are de-duped
by identical (total_credits, total_usage); per-key rolling windows (daily,
weekly, monthly) are summed. Sources:
  GET /api/v1/auth/key  -> per-key usage_daily / usage_weekly / usage_monthly,
                           limit / limit_reset / limit_remaining
  GET /api/v1/credits   -> account lifetime usage + top-up (de-duped)
Hourly is computed locally: the (monotonic) account lifetime total is logged on
every run and differenced against the sample at/just before the current hour.

Configuration (first match wins):
  $OPENROUTER_API_KEY / $OPENROUTER_KEY
  ~/.config/openrouter-cost/conf.json:  {"api_keys": ["sk-...", "sk-..."]}
  ~/.config/openrouter-cost/key         (single key on one line)

Output: ~/.local/state/openrouter-cost/overview.json
        ~/.local/state/openrouter-cost/history.jsonl
Stdlib only.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

HOME = os.path.expanduser("~")
CONF = os.path.join(HOME, ".config", "openrouter-cost", "conf.json")
KEYFILE = os.path.join(HOME, ".config", "openrouter-cost", "key")
STATE_DIR = os.path.join(HOME, ".local", "state", "openrouter-cost")
OUT = os.path.join(STATE_DIR, "overview.json")
HISTORY = os.path.join(STATE_DIR, "history.jsonl")
API = "https://openrouter.ai"


def load_keys():
    keys = []
    add = lambda k: k and k.startswith("sk-") and k not in keys and keys.append(k)
    for v in (os.environ.get("OPENROUTER_API_KEY"), os.environ.get("OPENROUTER_KEY")):
        if v:
            add(v.strip())
    if os.path.exists(CONF):
        try:
            j = json.load(open(CONF))
            got = j.get("api_keys") if isinstance(j.get("api_keys"), list) else (
                [j["api_key"]] if j.get("api_key") else [])
            for k in got:
                add(str(k).strip())
        except Exception:
            pass
    if os.path.exists(KEYFILE):
        add(open(KEYFILE).read().strip())
    return keys


def load_names(keys):
    try:
        j = json.load(open(CONF))
        ns = j.get("names") or []
        return {k: str(n) for k, n in zip(keys, ns) if n}
    except Exception:
        return {}


def fetch(key, path):
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def load_history():
    samples = []
    if os.path.exists(HISTORY):
        try:
            for line in open(HISTORY):
                line = line.strip()
                if not line:
                    continue
                j = json.loads(line)
                if j.get("v") == 2:  # discard pre-v2 samples (unit mismatch)
                    samples.append([j["ts"], num(j["usage"])])
        except Exception:
            samples = []
    return samples


def save_history(samples):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(HISTORY, "w") as f:
        for ts, usage in samples:
            f.write(json.dumps({"v": 2, "ts": ts, "usage": usage}) + "\n")


def _parse(iso):
    try:
        return datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None


def hour_usage(samples, total_now, now):
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    best = None
    for ts, u in samples:
        dt = _parse(ts)
        if dt is not None and dt <= hour_start and (best is None or dt > best[0]):
            best = (dt, u)
    return None if best is None else max(0.0, total_now - best[1])


def main():
    keys = load_keys()
    names = load_names(keys)
    now = datetime.now().astimezone()
    if not keys:
        _write({"error": "no-api-key", "updatedAt": now.isoformat()})
        print("openrouter-cost: no API key configured")
        return 1

    win = {"daily": 0.0, "weekly": 0.0, "monthly": 0.0}
    limit = {"amount": 0.0, "remaining": 0.0, "reset": None}
    acct_credits = 0.0
    acct_usage = 0.0
    seen = set()  # de-dupe identical accounts shared by several keys
    errors = []
    keys_info = []

    for key in keys:
        try:
            kd = (fetch(key, "/api/v1/auth/key") or {}).get("data") or {}
            cd = (fetch(key, "/api/v1/credits") or {}).get("data") or {}
        except urllib.error.HTTPError as e:
            errors.append(_http_error(e))
            continue
        except Exception as e:
            errors.append(str(e))
            continue

        win["daily"] += num(kd.get("usage_daily"))
        win["weekly"] += num(kd.get("usage_weekly"))
        win["monthly"] += num(kd.get("usage_monthly"))
        limit["amount"] += num(kd.get("limit"))
        limit["remaining"] += num(kd.get("limit_remaining"))
        if limit["reset"] is None and kd.get("limit_reset"):
            limit["reset"] = str(kd.get("limit_reset"))

        k_amt = num(kd.get("limit"))
        k_rem = num(kd.get("limit_remaining"))
        k_used = max(0.0, k_amt - k_rem)
        keys_info.append({
            "label": names.get(key) or (kd.get("label") or "key").split("...")[0],
            "daily": num(kd.get("usage_daily")),
            "weekly": num(kd.get("usage_weekly")),
            "monthly": num(kd.get("usage_monthly")),
            "limit": k_amt,
            "remaining": k_rem,
            "used": k_used,
            "percent": round(min(100.0, k_used / k_amt * 100), 1) if k_amt > 0 else 0.0,
            "reset": kd.get("limit_reset") or "monthly",
        })

        acct_key = kd.get("creator_user_id") or str(
            (round(num(cd.get("total_credits")), 3), round(num(cd.get("total_usage")), 3)))
        if acct_key not in seen:
            seen.add(acct_key)
            acct_credits += num(cd.get("total_credits"))
            acct_usage += num(cd.get("total_usage"))

        print("openrouter-cost: key %s: d=%.2f wk=%.2f mo=%.2f lim=%.0f/%s acct=%.1f/%.1f" % (
            (kd.get("label") or "?").split("...")[0], num(kd.get("usage_daily")),
            num(kd.get("usage_weekly")), num(kd.get("usage_monthly")),
            num(kd.get("limit")), limit["reset"], acct_usage, acct_credits))

    if not errors and not seen:
        errors.append("all keys returned empty data")

    limit_used = max(0.0, limit["amount"] - limit["remaining"])
    limit_rec = None
    if limit["amount"] > 0:
        limit_rec = {
            "amount": limit["amount"], "used": limit_used,
            "remaining": limit["remaining"],
            "percent": round(min(100.0, limit_used / limit["amount"] * 100), 1),
            "reset": limit["reset"] or "monthly",
        }

    # Hourly: diff the monotonic account lifetime total.
    samples = [s for s in load_history() if (lambda iso: (_parse(iso) or now) >= now - timedelta(hours=25))(s[0])]
    samples.append([now.isoformat(), acct_usage])
    save_history(samples[-288:])
    hr = hour_usage(samples, acct_usage, now)

    rec = {
        "hour": {"cost": hr},
        "today": {"cost": win["daily"]},
        "week": {"cost": win["weekly"]},
        "month": {"cost": win["monthly"]},
        "all": {"cost": acct_usage},           # account lifetime (de-duped)
        "limit": limit_rec,
        "credits": {"total": acct_credits, "used": acct_usage},
        "accounts": len(seen),
        "keys": len(keys),
        "keyBreakdown": keys_info,
        "key0": keys_info[0] if len(keys_info) > 0 else None,
        "key1": keys_info[1] if len(keys_info) > 1 else None,
        "key2": keys_info[2] if len(keys_info) > 2 else None,
        "key3": keys_info[3] if len(keys_info) > 3 else None,
        "updatedAt": now.isoformat(),
        "error": errors[0] if errors else None,
        "apiKeyConfigured": True,
    }
    _write(rec)
    if errors:
        print("openrouter-cost: %d key(s) failed: %s" % (len(errors), errors[0]))
        return 1
    print("openrouter-cost: ok (%d key(s), %d account(s))" % (len(keys), len(seen)))
    return 0


def _http_error(e):
    try:
        j = json.loads(e.read().decode())
        err = j.get("error") or {}
        return "%s: %s" % (e.code, err.get("message", e.reason))
    except Exception:
        return "%s %s" % (e.code, e.reason)


def _write(rec):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f, indent=2)
    os.replace(tmp, OUT)


if __name__ == "__main__":
    sys.exit(main())