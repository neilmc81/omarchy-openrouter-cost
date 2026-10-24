# Changelog

## 0.1.4

- One Management key now covers everything: the widget lists every API key
  on your account (`GET /api/v1/keys`) with its spend and limit, so you don't
  have to add your app keys one by one. Normal API keys still work as before.
- The installer asks for a Management key, explains why, and says which kind
  of key you pasted after checking it. A key from `OPENROUTER_API_KEY` is now
  saved to `~/.config/openrouter-cost/key` (mode 600) when no key is
  configured, so the bar can see it.
- New `--no-prompt` (or `OPENROUTER_COST_NO_PROMPT=1`) and `--no-verify`
  installer options. A key in an unusual format gets a warning instead of
  being refused. Skipping prints one line on how to add a key later.
- The dropdown's no-key message now points to the installer and the key file.
- Tests: `tests/test_install.sh` (installer key step, temp HOME, fake key) and
  `tests/test_update.py` (Management and normal key handling, no network).

## 0.1.3

- The bar now shows the OpenRouter mark instead of the `OR` text label. It's
  drawn natively in the bar's text colour, so it follows your theme. `⚠` (no
  key) and `!` (error) are unchanged.
- Icon from [Simple Icons](https://simpleicons.org) (CC0).

## 0.1.2

- Omarchy 4.5 compatibility: the bar label (`OR`, `!`) now renders at normal text size on Omarchy 4.5, which scales `BarIconButton` text down to icon size. Uses `WidgetButton`, which works the same on 4.0.6.
- Manifest declares `defaultSection: right`, so `omarchy-plugin-add` places the widget on the right.

## 0.1.1

- One-line installer (`install.sh`): clones or updates the plugin, prompts
  for an API key with hidden input, registers the widget in `shell.json`
  (with a backup), checks the key and restarts the shell.
- Uninstaller (`uninstall.sh`): removes the bar entry, the plugin clone and
  cached data; keeps your API keys unless you say yes or pass `--purge`.

## 0.1.0

- First release: bar status label and dropdown with last-hour, today, week
  and month spend, per-key limits and credit balance.
