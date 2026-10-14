#!/bin/sh
# What /orkline runs (skills/orkline/SKILL.md):
#   town.sh status    whether Orkline is installed, and uv
#   town.sh open      opens the town, in the background
#   town.sh install   uv (when missing) and Orkline from PyPI; run only after the person said yes
. "$(dirname "$0")/find-orkline.sh"
UV_INSTALLER="https://astral.sh/uv/install.sh"
PACKAGE="orkline[gui]"

case "${1:-status}" in
  status)
    if [ -n "$ORKLINE" ]; then
      echo "installed: $ORKLINE ($("$ORKLINE" --version 2>/dev/null || echo "version unknown"))"
    else
      echo "missing: Orkline is not installed"
      if command -v uv >/dev/null 2>&1; then echo "uv: $(command -v uv)"; else echo "uv: missing"; fi
    fi ;;
  open)
    [ -n "$ORKLINE" ] || { echo "missing: Orkline is not installed"; exit 1; }
    nohup "$ORKLINE" >/dev/null 2>&1 &
    echo "opening the town: $ORKLINE (in $(pwd))" ;;
  install)
    if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
      echo "installing uv from $UV_INSTALLER"
      curl -LsSf "$UV_INSTALLER" | sh || { echo "uv did not install"; exit 1; }
    fi
    UV=$(command -v uv 2>/dev/null || echo "$HOME/.local/bin/uv")
    echo "installing $PACKAGE with $UV tool install"
    "$UV" tool install "$PACKAGE" || { echo "Orkline did not install"; exit 1; }
    . "$(dirname "$0")/find-orkline.sh"
    echo "installed: ${ORKLINE:-$HOME/.local/bin/orkline}" ;;
  *)
    echo "usage: town.sh status|open|install"; exit 2 ;;
esac
