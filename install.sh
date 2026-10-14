#!/bin/sh
# Orkline's installer for macOS and Linux (docs/install.md):
#
#   curl -fsSL https://orkcraft.dev/install.sh | sh
#   curl -fsSL https://orkcraft.dev/install/<role>/<look> | sh     # the town opens on that class and look
#
# It puts uv in place (when it is not there yet), a Python for Orkline, and Orkline itself as a uv
# tool, then looks for the window toolkit and the AI tools. Each step is written to
# ~/.orkcraft/install.log. If you say yes, each step's outcome goes to Orkline's usage proxy as well:
# which step, whether it worked, how long it took (a bucket) and, when it failed, the kind of error
# (a word from a closed list). Never a path, a name, an error's text or your IP address.
#
#   sh install.sh --report      say yes without being asked     (ORKCRAFT_REPORT=1)
#   sh install.sh --no-report   say no without being asked      (ORKCRAFT_REPORT=0)
#
# Nothing is sent under DO_NOT_TRACK, ORKCRAFT_NO_USAGE or CI. ORKCRAFT_USAGE_DEBUG=1 prints each
# event instead of sending it. ORKCRAFT_INSTALL_FROM=<folder> installs that checkout instead of main.
set -u

INSTALLER="installer-1"                       # the installer's own version, in each event it sends
UV_VERSION="0.11.32"                          # the uv put in place when there is none
PYTHON="3.12"
REPO="https://github.com/Orkcraft/orkcraft"
ENDPOINT="${ORKCRAFT_USAGE_URL:-https://orkcraft-usage.vadim-sidoryk.workers.dev/v1/events}"
LOG_DIR="${HOME}/.orkcraft"
LOG="${LOG_DIR}/install.log"
STEP_OUT="${LOG_DIR}/install.step"

REPORT="${ORKCRAFT_REPORT:-}"
# The class and look picked on orkcraft.dev, handed to the town it opens. The server that hands this file
# out writes them here (…/install/<role>/<look>, tools/usage-worker/worker.js); --role / --look win.
ROLE=""
LOOK=""
OPEN=1                                        # open the town at the end, when there is a terminal
USAGE="sh install.sh [--report | --no-report] [--role ROLE] [--look camp|office] [--no-open]"
while [ $# -gt 0 ]; do
  case "$1" in
    --report) REPORT=1 ;;
    --no-report) REPORT=0 ;;
    --no-open) OPEN=0 ;;
    --role|--look)
      [ $# -ge 2 ] || { echo "orkline install: $1 needs a value" >&2; exit 2; }
      case "$2" in *[!a-z0-9_-]*|"") echo "orkline install: $1 takes a word such as engineer or camp" >&2; exit 2 ;; esac
      if [ "$1" = --role ]; then ROLE="$2"; else LOOK="$2"; fi
      shift ;;
    -h|--help) echo "${USAGE}"; echo "${REPO}/blob/main/docs/install.md"; exit 0 ;;
    *) echo "orkline install: unknown option $1 (${USAGE})" >&2; exit 2 ;;
  esac
  shift
done
case "$LOOK" in ""|camp|office) ;; *) echo "orkline install: --look is camp or office" >&2; exit 2 ;; esac

mkdir -p "$LOG_DIR" || { echo "orkline install: cannot write ${LOG_DIR}" >&2; exit 1; }
: > "$LOG"

# -- banner: tools/install_banner.py --
banner() {                                    # $1: the terminal's width in columns
  printf '     \033[0m\033[48;5;221m \033[0m \033[0m\033[48;5;221m  \033[0m \033[0m\033[48;5;221m \033[0m   \033[0m'; printf '\n'
  printf '  \033[0m\033[48;5;70m \033[0m \033[0m\033[48;5;70m        \033[0m \033[0m\033[48;5;70m \033[0m'; [ "$1" -ge 48 ] && printf '   \033[1mOrkline\033[0m'; printf '\n'
  printf '   \033[0m\033[48;5;70m  \033[0m\033[48;5;234m  \033[0m\033[48;5;70m  \033[0m\033[48;5;234m  \033[0m\033[48;5;70m  \033[0m \033[0m'; [ "$1" -ge 48 ] && printf '   The Warchief raises your camp'; printf '\n'
  printf '    \033[0m\033[48;5;70m \033[0m\033[48;5;253m \033[0m\033[48;5;70m    \033[0m\033[48;5;253m \033[0m\033[48;5;70m \033[0m  \033[0m'; [ "$1" -ge 48 ] && printf '   \033[2muv · Python · Orkline\033[0m'; printf '\n'
  printf '     \033[0m\033[48;5;70m      \033[0m   \033[0m'; printf '\n'
}
# -- end of banner --
# The terminal's width: the Warchief alone when his words would wrap, nothing when he would not fit.
COLS="$(stty size </dev/tty 2>/dev/null | cut -d' ' -f2)"
case "$COLS" in ""|*[!0-9]*) COLS="$(tput cols 2>/dev/null || echo 80)" ;; esac
case "$COLS" in ""|*[!0-9]*) COLS=80 ;; esac
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != dumb ] && [ "$COLS" -ge 16 ]; then
  echo; banner "$COLS"; echo
fi

say() { printf '%s\n' "$*"; printf '%s\n' "$*" >> "$LOG"; }

set_on() { case "$(printf '%s' "${1:-}" | tr 'A-Z' 'a-z')" in ""|0|false|no) return 1 ;; *) return 0 ;; esac; }

blocked() {
  set_on "${DO_NOT_TRACK:-}" && return 0
  set_on "${ORKCRAFT_NO_USAGE:-}" && return 0
  set_on "${CI:-}" && return 0
  return 1
}

# -- the question ------------------------------------------------------------------------------

ASKED=0                                       # 1: the person answered here; the app will not ask again
if blocked; then
  REPORT=0
elif [ -z "$REPORT" ]; then
  if (: </dev/tty) 2>/dev/null; then         # a terminal to ask in, also under curl | sh
    printf 'Send an anonymous report of how this install goes, and later which features you use?\n'
    printf 'Only step names, ok or failed, a time bucket and a kind of error; never paths, names or your IP.\n'
    printf 'Details: %s/blob/main/docs/install.md  [y/N] ' "$REPO"
    answer=""
    read -r answer </dev/tty || answer=""
    case "$answer" in y|Y|yes|Yes|YES) REPORT=1 ;; *) REPORT=0 ;; esac
    ASKED=1
  else
    REPORT=0                                  # nobody to ask: nothing is sent, the app asks later
  fi
else
  case "$REPORT" in 1|yes|true) REPORT=1 ;; *) REPORT=0 ;; esac
  ASKED=1
fi

INSTALL_ID=""
if [ "$REPORT" = 1 ]; then
  INSTALL_ID="$(od -An -N16 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')"
  [ "${#INSTALL_ID}" = 32 ] || REPORT=0
fi
SESSION_ID="$(date +%s)000"

case "$(uname -s)" in Darwin) OS=darwin ;; Linux) OS=linux ;; *) OS=unknown ;; esac
case "$(uname -m)" in x86_64|amd64) ARCH=x86_64 ;; arm64|aarch64) ARCH=arm64 ;; *) ARCH=other ;; esac

# -- events (docs/install.md; the same list as orkcraft/core/usage.py and tools/usage-worker/) ----

event() {                                     # event NAME '"key": value, …' (values from closed lists only)
  [ "$REPORT" = 1 ] || return 0
  body="{\"install_id\": \"${INSTALL_ID}\", \"session_id\": ${SESSION_ID}, \"app_version\": \"${INSTALLER}\", \"os\": \"${OS}\", \"python\": \"unknown\", \"events\": [{\"event\": \"$1\", \"time\": $(date +%s)000, \"props\": {$2}}]}"
  if set_on "${ORKCRAFT_USAGE_DEBUG:-}"; then
    printf 'orkcraft usage: %s\n' "$body" >&2
    return 0
  fi
  command -v curl >/dev/null 2>&1 || return 0
  curl -fsS -m 5 -o /dev/null -X POST "$ENDPOINT" -H "User-Agent: orkcraft/${INSTALLER}" \
    -H "Content-Type: application/json" --data "$body" >/dev/null 2>&1 || true
}

bucket() {                                    # seconds → <10 · 10-60 · 60-300 · 300+
  if [ "$1" -lt 10 ]; then echo "<10"; elif [ "$1" -lt 60 ]; then echo "10-60"
  elif [ "$1" -lt 300 ]; then echo "60-300"; else echo "300+"; fi
}

kind() {                                      # the kind of error in a step's output, from a closed list
  f="$1"
  if grep -qi 'no space left' "$f"; then echo disk_full
  elif grep -qiE 'permission denied|operation not permitted|EACCES' "$f"; then echo permission
  elif grep -qiE 'certificate|ssl|tls' "$f"; then echo tls
  elif grep -qiE 'could not resolve|failed to connect|connection (refused|reset)|network is unreachable|timed out|dns error|error sending request' "$f"; then echo network
  elif grep -qiE 'no (download|python) found|failed to (install|download) python|no interpreter found' "$f"; then echo python_download
  elif grep -qiE 'no solution found|unsatisfiable|because .* depends on' "$f"; then echo resolve_failed
  elif grep -qiE 'failed to build|build backend|error: command .* failed|compil' "$f"; then echo build_failed
  elif grep -qiE 'git.*(not found|failed)|xcrun: error|no developer tools' "$f"; then echo git_missing
  else echo unknown; fi
}

STARTED="$(date +%s)"
FAILED="none"

finish() {                                    # finish OK(true|false)
  took=$(( $(date +%s) - STARTED ))
  event install_finished "\"ok\": $1, \"seconds\": \"$(bucket "$took")\", \"failed_step\": \"${FAILED}\""
}

fail() {                                      # fail STEP: say what broke and how to tell us, then stop
  FAILED="$1"
  finish false
  say ""
  say "Orkline did not install: the ${1} step failed. What it said is in ${LOG}."
  say "Tell us, with that file attached: ${REPO}/issues/new?title=Install%20failed%3A%20${1}%20(${OS}%20${ARCH})"
  exit 1
}

step() {                                      # step NAME EXTRA_PROPS COMMAND…: run it, log it, send its outcome
  name="$1"; extra="$2"; shift 2
  t0="$(date +%s)"
  printf '\n== %s: %s\n' "$name" "$*" >> "$LOG"
  "$@" > "$STEP_OUT" 2>&1
  code=$?
  cat "$STEP_OUT" >> "$LOG"
  took=$(( $(date +%s) - t0 ))
  if [ "$code" = 0 ]; then
    event install_step "\"step\": \"${name}\", \"ok\": true, \"seconds\": \"$(bucket "$took")\"${extra}"
    return 0
  fi
  event install_step "\"step\": \"${name}\", \"ok\": false, \"seconds\": \"$(bucket "$took")\", \"error\": \"$(kind "$STEP_OUT")\"${extra}"
  return 1
}

# -- the steps ---------------------------------------------------------------------------------

say "Orkline installer (${OS} ${ARCH}); the log: ${LOG}"
if [ "$OS" = unknown ]; then
  say "This installer is for macOS and Linux. On Windows: pipx install \"orkcraft[gui] @ git+${REPO}\""
  exit 1
fi

export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
UPGRADE=false
command -v orkcraft >/dev/null 2>&1 && UPGRADE=true
event install_started "\"method\": \"sh\", \"arch\": \"${ARCH}\", \"upgrade\": ${UPGRADE}"

uv_install() {                               # fetched first, run after: a failed download fails the step
  command -v curl >/dev/null 2>&1 || { echo "curl not found"; return 1; }
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" -o "${LOG_DIR}/uv-install.sh" || return 1
  env UV_NO_MODIFY_PATH=1 sh "${LOG_DIR}/uv-install.sh"
  code=$?
  rm -f "${LOG_DIR}/uv-install.sh"
  return $code
}
uv_works() { uv --version 2>/dev/null | grep -q '^uv '; }   # a uv that answers, not an empty or broken file
if uv_works; then
  say "uv: found ($(uv --version 2>/dev/null))"
  event install_step "\"step\": \"uv\", \"ok\": true, \"seconds\": \"<10\", \"found\": true"
else
  say "uv: putting it in place…"
  step uv ', "found": false' uv_install || fail uv
  uv_works || { say "uv was put in ~/.local/bin but does not answer"; fail uv; }
fi

say "Python ${PYTHON}: making sure there is one for Orkline…"
step python '' uv python install "$PYTHON" || fail python

# A git checkout when git works (so `uv tool upgrade` follows main), else GitHub's archive of main.
SOURCE=git
if [ "$OS" = darwin ] && ! xcode-select -p >/dev/null 2>&1; then
  SOURCE=archive                              # macOS's git is a stub until the developer tools are in
elif ! git --version >/dev/null 2>&1; then
  SOURCE=archive
fi
if [ -n "${ORKCRAFT_INSTALL_FROM:-}" ]; then   # a checkout of its own (CI tests the commit it runs on)
  SOURCE=local; SPEC="orkcraft[gui] @ file://$(cd "$ORKCRAFT_INSTALL_FROM" && pwd)"
elif [ "$SOURCE" = git ]; then SPEC="orkcraft[gui] @ git+${REPO}"
else SPEC="orkcraft[gui] @ ${REPO}/archive/refs/heads/main.tar.gz"; fi
say "Orkline: installing from ${SOURCE}…"
step package ", \"source\": \"${SOURCE}\"" uv tool install --force --python "$PYTHON" "$SPEC" || fail package

uv tool update-shell >> "$LOG" 2>&1 || true   # ~/.local/bin on the PATH of new terminals
BIN="$(uv tool dir --bin 2>/dev/null || echo "${HOME}/.local/bin")"
ORKCRAFT="${BIN}/orkcraft"
[ -x "$ORKCRAFT" ] || ORKCRAFT="$(command -v orkcraft 2>/dev/null || echo orkcraft)"
step version '' "$ORKCRAFT" --version || fail version

# The window: pywebview and, on Linux, a web view it can use; without them the town opens in the browser.
PY="$(dirname "$(readlink -f "$ORKCRAFT" 2>/dev/null || echo "$ORKCRAFT")")/python"
WINDOW=browser
if [ -x "$PY" ] && "$PY" -c "import webview" >/dev/null 2>&1; then
  if [ "$OS" = darwin ]; then WINDOW=native
  elif "$PY" -c "import gi" >/dev/null 2>&1 || "$PY" -c "import qtpy" >/dev/null 2>&1; then WINDOW=native; fi
fi
event install_step "\"step\": \"window\", \"ok\": true, \"seconds\": \"<10\", \"window\": \"${WINDOW}\""
[ "$WINDOW" = native ] && say "Window: its own" || say "Window: none here; the town opens in your browser"

TOOLS=""
for t in claude codex agy; do
  if command -v "$t" >/dev/null 2>&1; then TOOLS="${TOOLS:+${TOOLS}, }\"$t\""; fi
done
event install_step "\"step\": \"agents\", \"ok\": true, \"seconds\": \"<10\", \"tools\": [${TOOLS}]"
if [ -n "$TOOLS" ]; then say "AI tools found: $(echo "$TOOLS" | tr -d '"')"
else say "No AI tool found yet (claude, codex or agy): Orkline says how to add one when it opens."; fi

# One answer for both: what was said here is the app's answer too, with the same install id.
if [ "$ASKED" = 1 ]; then
  if [ "$REPORT" = 1 ]; then "$ORKCRAFT" usage on --id "$INSTALL_ID" >> "$LOG" 2>&1 || true
  else "$ORKCRAFT" usage off >> "$LOG" 2>&1 || true; fi
fi

finish true
say ""
say "Orkline is installed. Next time: open a new terminal, go to a project and run: orkline"

# The town opens now, on the class and look picked on orkcraft.dev, when there is a terminal to hold it.
if [ "$OPEN" = 1 ] && [ -t 1 ] && (: </dev/tty) 2>/dev/null; then
  set -- 
  [ -n "$ROLE" ] && set -- "$@" --role "$ROLE"
  [ -n "$LOOK" ] && set -- "$@" --look "$LOOK"
  say "Opening the town…"
  exec "$ORKCRAFT" "$@" </dev/tty
elif [ -n "$ROLE$LOOK" ]; then
  say "To open it on your pick: orkline${ROLE:+ --role $ROLE}${LOOK:+ --look $LOOK}"
fi
