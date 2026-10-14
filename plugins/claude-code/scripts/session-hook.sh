#!/bin/sh
# Orkline's session log, as a Claude Code hook (SessionStart, UserPromptSubmit; hooks/hooks.json).
# Fails open: with Orkline missing, broken or too old, it says nothing and exits 0, so a session never
# notices it. The hook's payload on stdin goes to `orkline hooks session` (orkcraft/hooks/session.py),
# which records only in a project Orkline keeps and only once.
here=$(dirname "$0" 2>/dev/null) || exit 0
[ -r "$here/find-orkline.sh" ] || exit 0
. "$here/find-orkline.sh"
[ -n "$ORKLINE" ] || exit 0
"$ORKLINE" hooks session >/dev/null 2>&1
exit 0
