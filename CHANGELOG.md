# Changelog

## 0.1.1

- One-line installer (`install.sh`): clones or updates the plugin, prompts
  for an API key with hidden input, registers the widget in `shell.json`
  (with a backup), checks the key and restarts the shell.
- Uninstaller (`uninstall.sh`): removes the bar entry, the plugin clone and
  cached data; keeps your API keys unless you say yes or pass `--purge`.

## 0.1.0

- First release: bar status label and dropdown with last-hour, today, week
  and month spend, per-key limits and credit balance.
