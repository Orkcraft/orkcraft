# Sourced by the plugin's scripts: sets ORKLINE to the `orkline` (or older `orkcraft`) command, "" when
# Orkline is not installed. Claude Code may run hooks with a short PATH, so the usual install folders
# (uv's and pipx's ~/.local/bin, Homebrew's) are looked in too.
ORKLINE=""
for name in orkline orkcraft; do
  found=$(command -v "$name" 2>/dev/null) && [ -n "$found" ] && { ORKLINE=$found; break; }
done
if [ -z "$ORKLINE" ]; then
  for dir in "${XDG_BIN_HOME:-$HOME/.local/bin}" "$HOME/.local/bin" /opt/homebrew/bin /usr/local/bin; do
    for name in orkline orkcraft; do
      [ -x "$dir/$name" ] && { ORKLINE="$dir/$name"; break 2; }
    done
  done
fi
