#!/usr/bin/env bash
# Tests for the API key step of install.sh. Every run uses a throwaway HOME
# and a fake key, so your real config is never read or changed. Nothing is
# fetched from OpenRouter (--no-verify) and the shell isn't restarted.
#
#   bash tests/test_install.sh
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
INSTALL="$ROOT/install.sh"
REF=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)
FAKE="sk-or-v1-FAKE0123456789abcdef0123456789abcdef"
PASS=0 FAIL=0
TMPS=()
trap 'rm -rf "${TMPS[@]}"' EXIT

pass() { PASS=$((PASS + 1)); printf 'ok   %s\n' "$1"; }
fail() { FAIL=$((FAIL + 1)); printf 'FAIL %s\n' "$1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/     /'; }
check() { if eval "$2"; then pass "$1"; else fail "$1" "$OUT"; fi; }

new_home() {
  H=$(mktemp -d); TMPS+=("$H")
  mkdir -p "$H/.config/omarchy"
  printf '{\n  "bar": {\n    "layout": {\n      "right": []\n    }\n  }\n}\n' >"$H/.config/omarchy/shell.json"
  KEYFILE="$H/.config/openrouter-cost/key"
}

# Runs the installer in the temp HOME with no terminal. Extra env as "$@".
run_notty() {
  OUT=$(env -i PATH="$PATH" HOME="$H" "$@" OPENROUTER_COST_REPO="$ROOT" OPENROUTER_COST_REF="$REF" \
    setsid -w bash "$INSTALL" --no-restart --no-verify </dev/null 2>&1); RC=$?
}

# Runs the installer on a pseudo-terminal and types $1 at the key prompt.
# The typing waits a moment so it lands after the prompt (typed-ahead input
# is echoed by the terminal before the installer can hide it).
run_tty() {
  OUT=$({ sleep 3; printf '%s\n' "$1"; } | env -i PATH="$PATH" HOME="$H" TERM=dumb SHELL=/bin/bash \
    OPENROUTER_COST_REPO="$ROOT" OPENROUTER_COST_REF="$REF" \
    script -qec "bash '$INSTALL' --no-restart --no-verify" /dev/null 2>&1); RC=$?
}

mode() { stat -c %a "$1"; }

# 1. No terminal and no key: skips quietly with a hint, writes nothing.
new_home; run_notty
check "no tty: exits 0" '[ $RC -eq 0 ]'
check "no tty: no key file" '[ ! -e "$KEYFILE" ]'
check "no tty: says how to add it later" 'grep -q "add one later" <<<"$OUT"'

# 2. --no-prompt on a terminal: still doesn't ask.
new_home
OUT=$(printf '%s\n' "$FAKE" | env -i PATH="$PATH" HOME="$H" TERM=dumb SHELL=/bin/bash \
  OPENROUTER_COST_REPO="$ROOT" OPENROUTER_COST_REF="$REF" \
  script -qec "bash '$INSTALL' --no-prompt --no-restart --no-verify" /dev/null 2>&1); RC=$?
check "--no-prompt: no prompt shown" '! grep -q "Paste your" <<<"$OUT"'
check "--no-prompt: no key file" '[ ! -e "$KEYFILE" ]'

# 3. Key from the environment is saved, mode 600, never printed.
new_home; run_notty OPENROUTER_API_KEY="  $FAKE "
check "env: exits 0" '[ $RC -eq 0 ]'
check "env: key saved and trimmed" '[ "$(cat "$KEYFILE")" = "$FAKE" ]'
check "env: mode 600" '[ "$(mode "$KEYFILE")" = 600 ]'
check "env: one line" '[ "$(wc -l <"$KEYFILE")" -eq 1 ]'
check "env: key not in output" '! grep -qF "$FAKE" <<<"$OUT"'

# 4. A configured key is left alone, even if another one is offered.
run_notty OPENROUTER_API_KEY="sk-or-v1-OTHERKEY"
check "existing: key untouched" '[ "$(cat "$KEYFILE")" = "$FAKE" ]'
check "existing: says it's configured" 'grep -q "already configured" <<<"$OUT"'

# 5. Pasting at the prompt saves the key, hidden.
new_home; run_tty "$FAKE"
check "prompt: asks with the right text" 'grep -q "Paste your OpenRouter management key (press Enter to skip)" <<<"$OUT"'
check "prompt: key saved" '[ "$(cat "$KEYFILE" 2>/dev/null)" = "$FAKE" ]'
check "prompt: mode 600" '[ "$(mode "$KEYFILE")" = 600 ]'
check "prompt: key not echoed" '! grep -qF "$FAKE" <<<"$OUT"'

# 6. Pressing Enter skips with a hint.
new_home; run_tty ""
check "enter: no key file" '[ ! -e "$KEYFILE" ]'
check "enter: says how to add it later" 'grep -q "add one later" <<<"$OUT"'

# 7. An odd-looking key gets a warning but is still saved.
new_home; run_notty OPENROUTER_API_KEY="not-a-normal-key-123"
check "format: warns" 'grep -q "doesn.t look like an OpenRouter key" <<<"$OUT"'
check "format: still saved" '[ "$(cat "$KEYFILE")" = "not-a-normal-key-123" ]'

# 8. With the fake key saved, update.py reads it (no network: it just has to
#    find it and not report "no API key").
new_home; run_notty OPENROUTER_API_KEY="$FAKE"
OUT=$(env -i PATH="$PATH" HOME="$H" python3 -I -c "
import sys; sys.path.insert(0, '$ROOT'); import update; print(len(update.load_keys()))" 2>&1)
check "update.py finds the saved key" '[ "$OUT" = 1 ]'

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
