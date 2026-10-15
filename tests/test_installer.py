"""The installer (install.sh, docs/install.md): each step logged, its outcome sent only after a yes and
only as the events core/usage.py and the proxy know, the answer handed to the app with the same id.
Every run here has a stand-in uv (and curl), so nothing is downloaded."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from orkcraft.core import usage

SCRIPT = Path(__file__).resolve().parents[1] / "install.sh"

ORKCRAFT = """#!/bin/sh
case "$1" in
  --version) echo "orkcraft 9.9.9" ;;
  usage) echo "$*" >> "$HOME/usage-said" ;;
esac
"""

UV = """#!/bin/sh
echo "uv $*" >> "$HOME/uv-calls"
case "$1 $2" in
  "--version "*) echo "uv 0.0.0" ;;
  "python install") ;;
  "tool install")
    if [ -n "${FAKE_FAIL:-}" ]; then echo "$FAKE_FAIL" >&2; exit 2; fi
    mkdir -p "$HOME/.local/bin"
    cat > "$HOME/.local/bin/orkcraft" <<'EOF'
%s
EOF
    chmod +x "$HOME/.local/bin/orkcraft" ;;
  "tool update-shell") ;;
  "tool dir") echo "$HOME/.local/bin" ;;
esac
""" % ORKCRAFT.strip()


def _bin(folder: Path, name: str, text: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
    (folder / name).chmod(0o755)


def _run(tmp_path: Path, *args: str, uv: bool = True, env: dict | None = None):
    home, fake = tmp_path / "home", tmp_path / "bin"
    home.mkdir(exist_ok=True)
    if uv:
        _bin(fake, "uv", UV)
    _bin(fake, "claude", "#!/bin/sh\n")
    base = {"HOME": str(home), "PATH": f"{fake}:/usr/bin:/bin", "ORKCRAFT_USAGE_DEBUG": "1"}
    # A session of its own: no terminal to ask in, as under a pipe with no tty.
    done = subprocess.run(["sh", str(SCRIPT), *args], env={**base, **(env or {})}, capture_output=True,
                          text=True, timeout=60, start_new_session=True)
    events = [json.loads(line.split(": ", 1)[1]) for line in done.stderr.splitlines()
              if line.startswith("orkcraft usage: ")]
    return done, events, home


def _names(events):
    return [(b["events"][0]["event"], b["events"][0]["props"].get("step")) for b in events]


def test_a_yes_sends_each_step_as_the_proxy_knows_it_and_hands_the_id_to_the_app(tmp_path):
    done, events, home = _run(tmp_path, "--report")
    assert done.returncode == 0, done.stdout + done.stderr
    assert _names(events) == [("install_started", None), ("install_step", "uv"), ("install_step", "python"),
                              ("install_step", "package"), ("install_step", "version"),
                              ("install_step", "window"), ("install_step", "agents"), ("install_finished", None)]
    ids = {b["install_id"] for b in events}
    assert len(ids) == 1 and usage.ID.fullmatch(ids.pop() or "")
    for b in events:                     # every property is one the app's list and the proxy's allow
        e = b["events"][0]
        assert usage.clean(e["event"], e["props"]) == e["props"], e
        assert b["app_version"] == "installer-1" and b["os"] in ("linux", "darwin")
    agents = events[6]["events"][0]["props"]
    assert agents["tools"] == ["claude"]
    assert events[-1]["events"][0]["props"]["ok"] is True
    assert (home / "usage-said").read_text().split() == ["usage", "on", "--id", events[0]["install_id"]]
    assert "== package: uv tool install" in (home / ".orkcraft" / "install.log").read_text()


def test_a_failed_step_says_its_kind_of_error_and_where_to_tell_us(tmp_path):
    done, events, home = _run(tmp_path, "--report",
                              env={"FAKE_FAIL": "error: Failed to connect to github.com/me/secret-path"})
    assert done.returncode == 1
    package = events[-2]["events"][0]
    assert package["props"] == {"step": "package", "ok": False, "seconds": "<10", "error": "network",
                                "source": "git"}
    assert events[-1]["events"][0]["props"]["failed_step"] == "package"
    assert "secret-path" not in done.stderr                    # the error's text stays in the log
    assert "secret-path" in (home / ".orkcraft" / "install.log").read_text()
    assert "issues/new?title=Install%20failed%3A%20package" in done.stdout
    assert not (home / "usage-said").exists()


@pytest.mark.parametrize("args, env", [((), {}), (("--no-report",), {}), (("--report",), {"DO_NOT_TRACK": "1"}),
                                       (("--report",), {"CI": "true"}), (("--report",), {"ORKCRAFT_NO_USAGE": "1"})])
def test_nothing_is_sent_without_a_yes_or_where_tracking_is_off(tmp_path, args, env):
    done, events, home = _run(tmp_path, *args, env=env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert events == []
    said = (home / "usage-said").read_text().split() if (home / "usage-said").exists() else []
    # A no said here is the app's answer; no question asked (no terminal, or tracking off) leaves it to the app.
    assert said == (["usage", "off"] if args == ("--no-report",) else [])


def test_without_uv_it_puts_the_pinned_one_in_place(tmp_path):
    home = tmp_path / "home"
    curl = f"""#!/bin/sh
echo "curl $*" >> "{home}/curl-calls"
out=/dev/stdout
while [ $# -gt 0 ]; do [ "$1" = -o ] && out="$2"; shift; done
cat > "$out" <<'EOS'
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/uv" <<'UVEOF'
{UV.strip()}
UVEOF
chmod +x "$HOME/.local/bin/uv"
EOS
"""
    home.mkdir()
    _bin(tmp_path / "bin", "curl", curl)
    done, events, home = _run(tmp_path, "--report", uv=False)
    assert done.returncode == 0, done.stdout + done.stderr
    assert events[1]["events"][0]["props"] == {"step": "uv", "ok": True, "seconds": "<10", "found": False}
    assert "https://astral.sh/uv/" in (home / "curl-calls").read_text()


def test_the_proxy_and_the_app_list_the_same_install_steps_and_errors():
    js = (Path(__file__).resolve().parents[1] / "tools" / "usage-worker" / "worker.js").read_text(encoding="utf-8")
    import re
    listed = lambda name: re.findall(r'"(\w+)"', re.search(rf"const {name} = \[(.*?)\];", js, re.S).group(1))  # noqa: E731
    assert listed("STEPS") == list(usage.INSTALL_STEPS)
    assert listed("ERRORS") == list(usage.INSTALL_ERRORS)
    text = SCRIPT.read_text(encoding="utf-8")
    assert set(re.findall(r"then echo (\w+)", text)) | {"unknown"} == set(usage.INSTALL_ERRORS)
    sent = set(re.findall(r'^\s*step (\w+) ', text, re.M)) | set(re.findall(r'"step\\": \\"(\w+)\\"', text))
    assert sent == set(usage.INSTALL_STEPS)


def test_the_script_is_plain_posix_sh():
    for shell in ("dash", "bash"):
        if any(Path(d, shell).exists() for d in os.environ.get("PATH", "").split(os.pathsep)):
            assert subprocess.run([shell, "-n", str(SCRIPT)]).returncode == 0


def test_a_pick_from_orkcraft_dev_is_said_back_when_the_town_cannot_open_here(tmp_path):
    done, events, home = _run(tmp_path, "--no-report", "--role", "engineer", "--look", "office")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "To open it on your pick: orkline --role engineer --look office" in done.stdout
    assert "\x1b[" not in done.stdout                  # no terminal: no Workchief in colour, no escapes in the log


@pytest.mark.parametrize("args", [("--look", "necropolis"), ("--role",), ("--role", "x; rm -rf ~"), ("--wat",)])
def test_a_wrong_option_stops_before_anything_is_installed(tmp_path, args):
    done, events, home = _run(tmp_path, "--no-report", *args)
    assert done.returncode == 2 and not (home / "uv-calls").exists()


def test_the_banner_is_the_warchiefs_sprite_as_drawn_now():
    pytest.importorskip("PIL")
    import sys
    sys.path.insert(0, str(SCRIPT.parent / "tools"))
    try:
        import install_banner
    finally:
        sys.path.pop(0)
    assert install_banner.block() in SCRIPT.read_text(encoding="utf-8")   # run tools/install_banner.py after a redraw


def test_a_failed_download_of_uv_fails_its_step_as_a_network_error(tmp_path):
    _bin(tmp_path / "bin", "curl", "#!/bin/sh\necho 'curl: (6) Could not resolve host: astral.sh' >&2\nexit 6\n")
    done, events, home = _run(tmp_path, "--report", uv=False)
    assert done.returncode == 1
    assert events[1]["events"][0]["props"] == {"step": "uv", "ok": False, "seconds": "<10", "error": "network",
                                               "found": False}
    assert "does not answer" not in done.stdout


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node is not installed")
def test_the_proxy_writes_the_pick_into_the_installer_so_the_command_needs_no_options(tmp_path):
    worker = Path(__file__).resolve().parents[1] / "tools" / "usage-worker" / "worker.js"
    (tmp_path / "worker.mjs").write_text(worker.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "run.mjs").write_text("""
import worker from "./worker.mjs";
import { readFileSync } from "node:fs";
const script = readFileSync(process.argv[2], "utf8");
globalThis.fetch = async () => new Response(script, { status: 200 });
const out = {};
for (const q of ["?role=peon&look=office", "?role=x%22%3B%20rm%20-rf%20~&look=necropolis", ""]) {
  const res = await worker.fetch(new Request("https://w.example/install.sh" + q), {});
  out[q] = await res.text();
}
console.log(JSON.stringify(out));
""", encoding="utf-8")
    got = json.loads(subprocess.run(["node", str(tmp_path / "run.mjs"), str(SCRIPT)], capture_output=True, text=True,
                                    check=True, timeout=30).stdout)
    picked = got["?role=peon&look=office"]
    assert 'ROLE="peon"' in picked and 'LOOK="office"' in picked
    assert got["?role=x%22%3B%20rm%20-rf%20~&look=necropolis"] == got[""] == SCRIPT.read_text(encoding="utf-8")
    served = tmp_path / "served.sh"
    served.write_text(picked, encoding="utf-8")
    home, fake = tmp_path / "home", tmp_path / "bin"
    home.mkdir()
    _bin(fake, "uv", UV)
    done = subprocess.run(["sh", str(served)], env={"HOME": str(home), "PATH": f"{fake}:/usr/bin:/bin", "CI": "1"},
                          capture_output=True, text=True, timeout=60, start_new_session=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "To open it on your pick: orkline --role peon --look office" in done.stdout
