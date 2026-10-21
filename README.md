# OpenRouter API Cost — Omarchy bar widget

A live [OpenRouter](https://openrouter.ai) spend tracker for the Omarchy
status bar. The bar shows a small status label; clicking it opens a dropdown
with your spend for the **last hour**, **today**, **this week** and
**this month**, plus **per-key limits** and your **credit balance**.

![OpenRouter cost widget](assets/screenshot.png)

Tested on Omarchy 4.0.6-1.

## Features

- Bar status label:
  - `OR` — working, data is current
  - `⚠` — no API key configured
  - `!` — the last fetch failed (details in the dropdown)
- Dropdown: spend for the last hour, today, this week and this month
- Per-key limits for up to 3 keys: name, this week's spend and used/limit,
  with a progress bar. Each OpenRouter key has its own limit and reset
  period; the section header shows the first key's reset period.
- Credit balance (needs a Management key, see below)
- Aggregates spend across multiple API keys / accounts
- Auto-refreshes every 5 minutes, on click, and from a Refresh button

Not shown yet: the all-time (lifetime) spend is collected in
`overview.json` but isn't displayed in the dropdown.

## Regular keys vs. Management keys

OpenRouter's `/api/v1/credits` endpoint may need a
[Management key](https://openrouter.ai/settings/management-keys) and can
return 403 for a regular API key. **With a regular (non-Management) key, the
credit balance and last-hour figures show `—`, and the all-time figure is
empty.** Today, this week, this month and the per-key limits still work. Use a
Management key if you want the balance, all-time and last-hour figures.

## Requirements

- Omarchy (Quickshell-based shell with QML plugin support)
- An [OpenRouter API key](https://openrouter.ai/settings/keys)
- Python 3 (only for the `update.py` data fetcher; standard library only)

## Installation

The plugin folder **must be named `openrouter.cost`** (it matches the plugin
id in `manifest.json`).

```bash
# 1. Clone the plugin into your Omarchy plugins directory
git clone https://github.com/neilmc81/omarchy-openrouter-cost \
    ~/.config/omarchy/plugins/openrouter.cost

# 2. Add your API key (see "Configuration" for all options), e.g.
mkdir -p ~/.config/openrouter-cost
printf '%s\n' 'sk-or-v1-...' > ~/.config/openrouter-cost/key
chmod 600 ~/.config/openrouter-cost/key

# 3. Register the widget in ~/.config/omarchy/shell.json under "bar",
#    e.g. in "layout" → "right":
#      { "id": "openrouter.cost" }
#    then reload the shell:
omarchy restart shell
```

## Configuration

Keys are collected from all of these sources (duplicates are ignored):

| Source                                   | Format                                   |
|------------------------------------------|------------------------------------------|
| `$OPENROUTER_API_KEY`                    | one key                                  |
| `$OPENROUTER_KEY`                        | one key                                  |
| `~/.config/openrouter-cost/conf.json`    | `{"api_key": "sk-or-..."}` or `{"api_keys": ["sk-or-...", "sk-or-..."]}` |
| `~/.config/openrouter-cost/key`          | one key on a single line                 |

Only values starting with `sk-` are used.

In `conf.json` you can name your keys with an optional `names` array, in the
same order as the keys:

```json
{
  "api_keys": ["sk-or-...", "sk-or-..."],
  "names": ["Personal", "Work"]
}
```

`names` are matched by position across all keys found, including env vars; if
you mix `OPENROUTER_API_KEY` with `conf.json`, put all keys in `conf.json`.

Unnamed keys are shown as `Key 1`, `Key 2` and so on. Changes are picked up on
the next refresh (no shell restart needed).

## Security

- Keys are read only from the environment variables and files listed above,
  and are sent only to `openrouter.ai`.
- No part of a key is printed, logged, or written to `overview.json` or
  `history.jsonl`.
- The widget does **not** check file permissions. Protect your key files
  yourself:

  ```bash
  chmod 600 ~/.config/openrouter-cost/key ~/.config/openrouter-cost/conf.json
  ```

## Data source

The widget uses OpenRouter's own accounting endpoints:

- `GET /api/v1/auth/key` — `usage_daily`, `usage_weekly`, `usage_monthly`,
  plus `limit` / `limit_reset` / `limit_remaining` for each key
- `GET /api/v1/credits` — account balance and lifetime usage (may need a
  Management key; see above)

**Last hour** isn't available from any endpoint, so it's computed locally: the
updater appends the account's lifetime usage to `history.jsonl` on each run
and subtracts the sample taken just before the current hour. It shows `—`
until the widget has run across an hour boundary, and always shows `—` if a
key can't read `/credits`. All amounts are OpenRouter credits, in US dollars.

## Manual refresh

```bash
~/.config/omarchy/plugins/openrouter.cost/update.py
```

The fetcher writes `overview.json` and `history.jsonl` to
`$XDG_STATE_HOME/openrouter-cost/` (default `~/.local/state/openrouter-cost/`).
The widget watches `overview.json` and updates live.

## Files

```
manifest.json   plugin metadata
BarWidget.qml   bar status label, 5 min auto-refresh
Panel.qml       click dropdown (spend, per-key limits, balance, refresh)
update.py       OpenRouter data fetcher
```

## License

[MIT](LICENSE)
