"""pi's 🛡️ Warder and session log: a TypeScript extension, since pi has no hook config of its own.

    path = pi_extension.write()        # $XDG_CACHE_HOME/orkcraft/pi/orkcraft.ts, with this Python in it
    pi -e <path> …                     # realm/harnesses.py passes it to every pi orkcraft starts

pi runs an extension's `tool_call` handler before each tool: it hands the call to
`python3 -m orkcraft.hooks.warder pi`, refuses a deny, asks the person in pi's UI on an ask (refuses
when no one is there, a headless run), and lets anything else go. `session_start` and each `input`
go to `orkcraft.hooks.session pi`. Our own failure never blocks a tool (pi blocks one whose handler
throws, so every call is caught). docs/design/harnesses.md
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SOURCE = """// orkcraft: the Warder and the session log for pi (written by orkcraft; it is rewritten, not edited).
import { spawnSync } from "node:child_process";

const PYTHON = __PYTHON__;

function call(module: string, payload: object): any {
  try {
    const r = spawnSync(PYTHON, ["-m", `orkcraft.hooks.${module}`, "pi"],
      { input: JSON.stringify(payload), encoding: "utf8", timeout: 10000 });
    return JSON.parse((r.stdout || "").trim() || "{}");
  } catch {
    return {};
  }
}

function sid(ctx: any): string {
  try { return String(ctx.sessionManager.getSessionId() || ""); } catch { return ""; }
}

function file(ctx: any): string {
  try { return String(ctx.sessionManager.getSessionFile() || ""); } catch { return ""; }
}

export default function (pi: any) {
  pi.on("tool_call", async (event: any, ctx: any) => {
    const v = call("warder", { hook_event_name: "PreToolUse", tool_name: event.toolName, tool_input: event.input,
                               cwd: ctx.cwd, session_id: sid(ctx) });
    if (v.decision === "deny") return { block: true, reason: v.reason };
    if (v.decision === "ask") {
      if (!ctx.hasUI) return { block: true, reason: `${v.reason} (no one here to ask, so it stops)` };
      const choice = await ctx.ui.select(`${v.reason}\\n\\nAllow it?`, ["Yes", "No"]);
      if (choice !== "Yes") return { block: true, reason: "Stopped by the operator" };
    }
    return undefined;
  });
  pi.on("session_start", async (event: any, ctx: any) => {
    call("session", { hook_event_name: "SessionStart", session_id: sid(ctx), cwd: ctx.cwd, transcript_path: file(ctx) });
  });
  pi.on("input", async (event: any, ctx: any) => {
    call("session", { hook_event_name: "UserPromptSubmit", session_id: sid(ctx), cwd: ctx.cwd,
                      transcript_path: file(ctx), prompt: String(event.text || "") });
    return { action: "continue" };
  });
}
"""


def source(python: str | None = None) -> str:
    return SOURCE.replace("__PYTHON__", json.dumps(python or sys.executable))


def cache_file() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", "").strip() or str(Path.home() / ".cache")
    return Path(base) / "orkcraft" / "pi" / "orkcraft.ts"


def write(path: Path | None = None) -> Path | None:
    """The extension at `path` (the cache file by default), rewritten only when it changed; None when it
    cannot be written (then pi runs without it, as it would without orkcraft)."""
    path = path or cache_file()
    text = source()
    try:
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    except OSError:
        return None
    return path
