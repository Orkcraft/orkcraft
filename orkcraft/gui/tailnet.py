"""Tailscale, when this machine runs it: how a phone on the road reaches the town at home
(docs/design/phone-places.md §3).

    tail = find()           # Tail("100.101.102.103", "town.tail1234.ts.net"), or None
    cert(tail)              # the machine's *.ts.net certificate, as `tailscale cert` makes it, or None

The town never runs a tailnet of its own: it finds the one the person installed (the `tailscale` command,
logged in and running) and listens on its address too, beside the LAN's. With HTTPS certificates on in the
tailnet, `tailscale cert` gives the machine's name a certificate any phone trusts as it is, so a client that
cannot pin one (Shortcuts, Tasker) still speaks HTTPS to the town. Never Funnel: that makes an address
public, and a phone needs the tailnet only. `ORKCRAFT_TAILSCALE=off` leaves Tailscale alone.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from orkcraft import env, settings

ENV = "TAILSCALE"
TIMEOUT_S = 10
CERT_DAYS = 30           # Let's Encrypt's certificates last 90 days: asked again after 30
MAC_APP = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"


@dataclass(frozen=True)
class Tail:
    ip: str              # this machine's IPv4 address in the tailnet (100.x.y.z)
    name: str = ""       # its MagicDNS name (town.tail1234.ts.net), "" without MagicDNS


def command() -> str | None:
    """The `tailscale` command: on the PATH, or inside the macOS app."""
    return shutil.which("tailscale") or (MAC_APP if os.path.isfile(MAC_APP) else None)


def off() -> bool:
    return str(env.getenv(ENV) or "").strip().lower() in ("0", "off", "no", "false")


def find(runner=None) -> Tail | None:
    """This machine in its tailnet while Tailscale runs and is logged in; None otherwise."""
    if off():
        return None
    exe = command() if runner is None else "tailscale"
    if exe is None:
        return None
    try:
        out = (runner or subprocess.run)([exe, "status", "--json"], capture_output=True, text=True, timeout=TIMEOUT_S)
        data = json.loads(out.stdout or "{}") if out.returncode == 0 else {}
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    me = data.get("Self") if isinstance(data, dict) and data.get("BackendState") == "Running" else None
    if not isinstance(me, dict):
        return None
    ips = [str(ip) for ip in me.get("TailscaleIPs") or [] if ":" not in str(ip)]
    if not ips:
        return None
    return Tail(ips[0], str(me.get("DNSName") or "").rstrip(".").lower())


def paths(folder: Path | None = None) -> tuple[Path, Path]:
    folder = folder or settings.path().parent
    return folder / "tailnet.crt", folder / "tailnet.key"


def cert(tail: Tail, folder: Path | None = None, runner=None, now: float | None = None) -> tuple[Path, Path] | None:
    """The machine's *.ts.net certificate and key, kept beside the settings (0600) and asked again after
    CERT_DAYS; None without MagicDNS or with HTTPS certificates off in the tailnet."""
    if not tail.name.endswith(".ts.net"):
        return None
    crt, key = paths(folder)
    now = time.time() if now is None else now
    try:
        if crt.is_file() and key.is_file() and now - crt.stat().st_mtime < CERT_DAYS * 86400:
            return crt, key
    except OSError:
        pass
    exe = command() if runner is None else "tailscale"
    if exe is None:
        return None
    crt.parent.mkdir(parents=True, exist_ok=True)
    try:
        out = (runner or subprocess.run)([exe, "cert", "--cert-file", str(crt), "--key-file", str(key), tail.name],
                                         capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not (crt.is_file() and key.is_file()):
        return None
    for p in (crt, key):
        try:
            p.chmod(0o600)
        except OSError:
            pass
    return crt, key
