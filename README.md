# OpenRouter API Cost — Omarchy bar widget

A live [OpenRouter](https://openrouter.ai) spend tracker for the Omarchy
status bar. The bar icon shows **today's spend**; clicking opens a dropdown
with the current **hour**, **today**, **this week**, **this month**, and
**all-time** cost, plus your **weekly limit** and **account balance**.



## Features

- Live spend in the bar: hourly, daily, weekly, monthly, all-time
- Weekly credit limit and remaining balance
- Aggregates cost across multiple API keys / accounts
- Hourly figure computed locally from a rolling history — no pagination hacks
- Auto-refreshes every 5 minutes, on click, and from a manual Refresh button

## Requirements

- Omarchy (Quickshell-based shell with QML plugin support)
- An [OpenRouter API key](https://openrouter.ai/account/keys)
- Python 3 (only for the `update.py` data fetcher)

## Installation

```bash
# 1. Clone the plugin into your Omarchy plugins directory
git clone https://github.com/neilmc81/omarchy-openrouter-cost \
    ~/.config/omarchy/plugins/openrouter.cost

# 2. Add your API key(s)
#    Either set the environment variable OPENROUTER_API_KEY, or create
#    ~/.config/openrouter-cost/conf.json:
#    { "api_keys": ["sk-or-...", "sk-or-..."] }

# 3. Register the widget in ~/.config/omarchy/shell.json (bar section),
#    then reload the shell:
#    omarchy restart shell
```

> **Security:** key files are read with 0600 permissions and match the OpenRouter
> `sk-or-v1-` format. Keys are never written into the plugin directory and
> never logged.

## Configuration

Keys and limits live in `~/.config/openrouter-cost/conf.json`:

| Key                    | Purpose                             |
|------------------------|-------------------------------------|
| `api_keys` (array)     | One or more OpenRouter keys         |
| `weekly_limit_usd`     | Optional weekly cap shown in the UI |

A single key may also be provided via `$OPENROUTER_API_KEY`.
Overrides are picked up on the next refresh (no shell restart needed).

## Data source

OpenRouter exposes no public per-request history list (the `/generation`
endpoint requires an id), so the widget uses the account's own accounting
endpoints:

- `GET /api/v1/auth/key` — `usage` (all-time), `usage_daily`, `usage_weekly`,
  `usage_monthly`, plus `limit` / `limit_reset` / `limit_remaining`
- `GET /api/v1/credits` — top-up balance

**Hourly** is not available from any endpoint, so it is computed locally: the
updater appends the live usage total to `history.jsonl` each run and diffs the
sample taken just before the current hour. It shows `—` until the widget has
run across an hour boundary. All cost values are OpenRouter credits,
denominated in US dollars.

## Manual refresh

```bash
python3 ~/.config/omarchy/plugins/openrouter.cost/update.py
```

The fetcher writes `$XDG_STATE_HOME/openrouter-cost/overview.json`, which the
widget watches and re-renders live.

## Files

```
manifest.json   plugin metadata
BarWidget.qml   bar icon (today's spend), 5 min auto-refresh
Panel.qml       click dropdown (hourly → all-time, limit, balance, refresh)
update.py       OpenRouter data fetcher
```

## License

[MIT](LICENSE)