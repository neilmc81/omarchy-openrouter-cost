#!/usr/bin/env python3
"""
OpenRouter cost/usage updater for the Omarchy top bar plugin `openrouter.cost`.

With a Management key, lists every API key on the account (GET /api/v1/keys)
and reports each one, so a single key covers everything. Otherwise it
aggregates cost across ALL configured OpenRouter API keys. Keys can share one
OpenRouter account, so account-level (lifetime / balance) figures are de-duped
by identical (total_credits, total_usage); per-key rolling windows (daily,
weekly, monthly) are summed. Sources:
  GET /api/v1/auth/key  -> per-key usage_daily / usage_weekly / usage_monthly,
                           limit / limit_reset / limit_remaining
  GET /api/v1/credits   -> account lifetime usage + top-up (de-duped). Optional:
                           it may need a Management key and 403 for ordinary
                           keys; then balance/lifetime/hourly are null and the
                           other figures are still reported.
Hourly is computed locally: the (monotonic) account lifetime total is logged on
every run and differenced against the sample at/just before the current hour.

Configuration (all sources are combined; a working Management key replaces
the per-key view, so app keys configured next to it aren't counted twice):
  $OPENROUTER_API_KEY / $OPENROUTER_KEY
  ~/.config/openrouter-cost/conf.json:  {"api_keys": ["sk-...", "sk-..."]}
  ~/.config/openrouter-cost/key         (single key on one line)

Output: $XDG_STATE_HOME/openrouter-cost/overview.json   (default ~/.local/state)
        $XDG_STATE_HOME/openrouter-cost/history.jsonl
No part of any API key is ever printed or written to these files.
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
STATE_DIR = os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local", "state"),
    "openrouter-cost")
OUT = os.path.join(STATE_DIR, "overview.json")
HISTORY = os.path.join(STATE_DIR, "history.jsonl")
API = "https://openrouter.ai"


def load_keys():
    keys = []
    add = lambda k: k and k not in keys and keys.append(k)
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


MAX_LIST_PAGES = 10  # 100 keys per page


def list_all_keys(key):
    """Every enabled API key on the account, via a Management key.

    Returns a list of key records (same usage/limit fields as /auth/key), or
    None if `key` isn't a working Management key.
    """
    out = []
    for page in range(MAX_LIST_PAGES):
        try:
            got = (fetch(key, "/api/v1/keys?offset=%d" % len(out)) or {}).get("data")
        except Exception:
            return None if page == 0 else out
        if not isinstance(got, list):
            return None if page == 0 else out
        out += [k for k in got if isinstance(k, dict) and not k.get("disabled")]
        if len(got) < 100:
            break
    return out


def is_management(kd):
    return bool(kd.get("is_management_key") or kd.get("is_provisioning_key"))


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
    credits_ok = True  # False once any key can't read /credits
    ok_keys = 0
    errors = []
    keys_info = []

    # Pass 1: look each key up. A Management key (flagged by /auth/key, or
    # refused there with 401/403 but able to list keys) switches to the
    # all-keys view.
    looked_up = []   # (index, key, kd or None, error or None)
    mgmt_key, listing = None, None
    for i, key in enumerate(keys):
        kd, err, refused = None, None, False
        try:
            kd = (fetch(key, "/api/v1/auth/key") or {}).get("data") or {}
        except urllib.error.HTTPError as e:
            err, refused = _http_error(e), e.code in (401, 403)
        except Exception as e:
            err = str(e)
        if (kd is not None and is_management(kd)) or refused:
            got = list_all_keys(key)
            if got is not None:
                mgmt_key, listing = key, got
                break
        looked_up.append((i, key, kd, err))

    def add_key(label, kd, cd, acct_key):
        nonlocal acct_credits, acct_usage
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
            "label": label,
            "daily": num(kd.get("usage_daily")),
            "weekly": num(kd.get("usage_weekly")),
            "monthly": num(kd.get("usage_monthly")),
            "limit": k_amt,
            "remaining": k_rem,
            "used": k_used,
            "percent": round(min(100.0, k_used / k_amt * 100), 1) if k_amt > 0 else 0.0,
            "reset": kd.get("limit_reset") or "monthly",
        })
        if acct_key not in seen:
            seen.add(acct_key)
            if cd is not None:
                acct_credits += num(cd.get("total_credits"))
                acct_usage += num(cd.get("total_usage"))

        print("openrouter-cost: %s: d=%.2f wk=%.2f mo=%.2f lim=%.0f/%s acct=%s" % (
            label, num(kd.get("usage_daily")),
            num(kd.get("usage_weekly")), num(kd.get("usage_monthly")),
            num(kd.get("limit")), limit["reset"],
            "%.1f/%.1f" % (acct_usage, acct_credits) if cd is not None else "n/a"))

    if mgmt_key is not None:
        try:
            cd = (fetch(mgmt_key, "/api/v1/credits") or {}).get("data") or None
        except Exception:
            cd = None
        credits_ok = cd is not None
        for n, kd in enumerate(listing):
            # "name" is the user's name for the key; "label" is a truncated
            # key, so it's never shown.
            label = str(kd.get("name") or "").strip() or "Key %d" % (n + 1)
            add_key(label, kd, cd if n == 0 else None, "management")
        ok_keys = len(listing) or 1
        if not listing:
            seen.add("management")

    for i, key, kd, err in ([] if mgmt_key is not None else looked_up):
        # Never derive a label from the key itself (nor OpenRouter's "label",
        # which defaults to a truncated key) -- use the configured name or Key N.
        label = names.get(key) or "Key %d" % (i + 1)
        if err is not None:
            errors.append(err)
            continue
        ok_keys += 1

        # /credits may need a Management key (403 for ordinary keys). Its
        # failure must not discard the per-key figures above.
        try:
            cd = (fetch(key, "/api/v1/credits") or {}).get("data") or None
        except Exception:
            cd = None

        if cd is not None:
            acct_key = kd.get("creator_user_id") or str(
                (round(num(cd.get("total_credits")), 3), round(num(cd.get("total_usage")), 3)))
        else:
            # No /credits data to de-dupe on: count this key as its own account
            # (unless /auth/key identified the owner), so "accounts" may over-count.
            credits_ok = False
            acct_key = kd.get("creator_user_id") or "key-%d" % i
        add_key(label, kd, cd, acct_key)

    if not errors and not ok_keys:
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

    # Hourly: diff the monotonic account lifetime total. Only meaningful when
    # every key could read /credits; a partial total would corrupt the history.
    hr = None
    if credits_ok and ok_keys:
        samples = [s for s in load_history() if (lambda iso: (_parse(iso) or now) >= now - timedelta(hours=25))(s[0])]
        samples.append([now.isoformat(), acct_usage])
        save_history(samples[-288:])
        hr = hour_usage(samples, acct_usage, now)

    rec = {
        "hour": {"cost": hr},
        "today": {"cost": win["daily"]},
        "week": {"cost": win["weekly"]},
        "month": {"cost": win["monthly"]},
        "all": {"cost": acct_usage if credits_ok else None},  # account lifetime (de-duped)
        "limit": limit_rec,
        # null balance -> panel shows "—" (key can't read /credits)
        "credits": {"total": acct_credits, "used": acct_usage} if credits_ok
                   else {"total": None, "used": None},
        "accounts": len(seen),
        "keys": len(listing) if mgmt_key is not None else len(keys),
        "managementKey": mgmt_key is not None,
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
    if mgmt_key is not None:
        print("openrouter-cost: ok (management key, %d key(s) on the account)" % len(listing))
    else:
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