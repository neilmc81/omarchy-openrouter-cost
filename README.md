# OpenRouter API Cost — Omarchy bar plugin

A live OpenRouter spend widget in the top bar:
bar icon = **today's spend**; click = dropdown with the current **hour**, **today**,
**this week**, **this month**, and **all-time** cost, plus your **weekly limit**
and **account balance**.

## Setup — done for you

Your OpenRouter API key(s) were found automatically and wired into
`~/.config/openrouter-cost/conf.json` (chmod 600). Two keys are currently
configured — the Hermes one (`~/.hermes/.env`) and the OpenCode one
(`~/.local/share/opencode/auth.json`) — and the widget **aggregates cost across
both** (they're separate accounts). Add/remove keys any time by editing
`conf.json`:

```json
{ "api_keys": ["sk-or-...", "sk-or-..."] }
```

(or drop a single key as `$OPENROUTER_API_KEY` / in `~/.config/openrouter-cost/key`).

Refresh happens automatically every 5 min, on click, and there's a Refresh button
in the panel. To fetch once manually:

    ~/.config/omarchy/plugins/openrouter.cost/update.py

## Data source (real, no pagination hacks)

OpenRouter exposes no public per-request history list (the `/generation` endpoint
requires an id), so this uses the account's own accounting:

- `GET /api/v1/auth/key` → `usage` (all-time), `usage_daily`, `usage_weekly`,
  `usage_monthly`, plus `limit` / `limit_reset` / `limit_remaining`.
- `GET /api/v1/credits` → top-up balance.
- **Hourly** isn't in any API response, so it's computed locally: the updater
  appends the live `usage` total to `history.jsonl` every run and diffs "now"
  vs the sample taken at/just before the current hour. It shows `—` until the
  widget has been running across an hour boundary (a few minutes of warm-up).

Cost values are OpenRouter credits, which are denominated in US dollars.

## Files

- `update.py`      — fetches OpenRouter data, writes `~/.local/state/openrouter-cost/overview.json`
- `BarWidget.qml`  — the bar icon (today's cost), auto-refreshes every 5 min
- `Panel.qml`      — the dropdown
- `manifest.json`  — plugin metadata

Registered in `~/.config/omarchy/shell.json` (center section, next to qwen cost).