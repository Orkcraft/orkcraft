"""Film one whole flow of the product for its landing page: a mail and a Slack message, triaged.

    python tools/landing_flow.py [--out DIR] [--mode camp|office] [--chromium PATH]

It builds the demo afresh, starts `orkcraft gui --demo --browser` (carts slowed down so each one is
seen on its road) and opens the Front Desk orkspace (demo/front_desk.py). Then it plays the flow
through the real road engine — the Watchtower hears each message as its source would send it (the
sandbox's `simulate` act), and every cart after that is the town's own:

    a mail arrives in the Inbox (a Watchtower) → Triage (a Clan Fire that routes): each member's
      verdict, the steward's route → "task for human" → one of the person's to-dos in Tasks (Task Fields)
    a Slack message arrives → Triage → "task for agent" → a task in To Do, which Tasks sends to
      Agents at work (a Barracks) → an ork works it (In Progress) → the result comes back (Done) and
      goes on to Results (a Loot Vault) with its links

At each step it takes a frame (1440×900 at twice the pixels, PNG) and the whole flow is recorded as
a video (mp4 when ffmpeg is found, else webm). Without --mode it films both looks, into OUT/camp and
OUT/office. Needs Playwright and a Chromium (tools/gallery.py says how).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gallery import ROOT, SCALE, VIEWPORT, free_port, launch  # noqa: E402

sys.path.insert(0, str(ROOT))
from orkcraft.demo import front_desk as fd  # noqa: E402

TRAVEL_S = 3.5               # how long a cart is on a road (the host's ORKCRAFT_CART_TRAVEL_S)
WORDING = re.compile(r"\b[Oo]rcs?\b|[Oo]rchestrat")


def start_gui(demo_dir: Path, port: int, log: Path, look: str) -> tuple[subprocess.Popen, str]:
    """`orkcraft gui --demo` in the browser mode, with carts that take TRAVEL_S on a road."""
    env = {**os.environ, "BROWSER": "true", "PYTHONUNBUFFERED": "1", "ORKCRAFT_CART_TRAVEL_S": str(TRAVEL_S)}
    proc = subprocess.Popen([sys.executable, "-m", "orkcraft", "--demo-reset", "gui", "--demo", str(demo_dir),
                             "--browser", "--port", str(port), "--look", look], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    end, seen = time.monotonic() + 240, []
    while time.monotonic() < end:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            continue
        seen.append(line)
        m = re.search(r"(http://127\.0\.0\.1:\d+/\?t=\S+)", line)
        if m:
            log.write_text("".join(seen), encoding="utf-8")
            return proc, m.group(1)
    proc.kill()
    raise RuntimeError("the GUI did not start:\n" + "".join(seen)[-2000:])


class Film:
    def __init__(self, page, out: Path) -> None:
        self.page, self.out, self.n = page, out, 0
        self.captions: list[dict] = []
        self.problems: list[str] = []
        page.on("pageerror", lambda e: self.problems.append(f"page error: {e}"))

    # -- the page ----------------------------------------------------------------------------------

    def wait(self, ms: float) -> None:
        self.page.wait_for_timeout(ms)

    def until(self, js: str, arg=None, timeout: float = 60_000) -> None:
        """Wait till `js` (a function of the snapshot `t` and `arg`) is true of the town the page shows."""
        self.page.wait_for_function(f"(arg) => {{ const t = window.__ork && window.__ork.town.value; "
                                    f"return !!t && ({js}); }}", arg=arg, timeout=timeout)

    def cart_on(self, road: str, title: str) -> None:
        """Wait till a cart carrying `title` leaves on `road` (a road key)."""
        self.until("t.carts.some(c => c.road === arg[0] && c.status !== 'filtered' && c.title.includes(arg[1]))",
                   [road, title])

    def simulate(self, message: dict) -> None:
        self.page.evaluate("([id, args]) => window.__ork.act(id, 'simulate', args)", [fd.POST, message])

    def open_card(self, bid: str) -> None:
        """The building's Command Card (one click on its hut)."""
        self.close()
        self.page.locator(f'.gui-hut[data-id="{bid}"] .gui-hut__title').first.click()
        self.page.wait_for_selector("section.gui-card", timeout=8000)
        self.wait(900)

    def open_full(self, bid: str) -> None:
        """The building's full window (a second click on its hut)."""
        self.open_card(bid)
        self.page.locator(f'.gui-hut[data-id="{bid}"] .gui-hut__title').first.click()
        self.page.wait_for_selector(".gui-full", timeout=8000)
        self.wait(1200)

    def close(self) -> None:
        for _ in range(3):
            if not self.page.locator(".gui-full, section.gui-card").count():
                return
            self.page.evaluate("document.activeElement && document.activeElement.blur()")
            self.page.keyboard.press("Escape")
            self.wait(350)

    def frame(self, name: str, caption: str) -> None:
        self.n += 1
        file = f"{self.n:02d}-{name}.png"
        self.page.screenshot(path=str(self.out / file))
        self.captions.append({"file": file, "caption": caption})
        text = self.page.locator("body").inner_text()
        for m in sorted(set(WORDING.findall(text))):
            self.problems.append(f"{file}: “{m}” where a person reads")
        print(f"  {file}  {caption}", flush=True)

    # -- the flow ----------------------------------------------------------------------------------

    def settle(self, look: str) -> None:
        """Before the first frame: the questions other orkspaces' orks wait with are answered (the demo seeds
        two), so the counters say nothing of them."""
        try:                                             # the orks' screens are read a moment after the start
            self.until("(t.alerts || []).length > 0", timeout=12_000)
        except Exception:
            pass
        for _ in range(5):
            alerts = self.page.evaluate("() => window.__ork.town.value.alerts || []")
            for a in alerts:
                if a.get("options"):
                    self.page.evaluate("([id, key]) => window.__ork.command('orders.answer', {id, key}).catch(() => {})",
                                       [a["id"], a["options"][0][0]])
            if not alerts:
                break
            self.wait(2000)
        self.wait(800)

    def strip(self, shown: bool) -> None:
        """The film frames a building's Command Card alone: Info and its orks below it say nothing new here."""
        self.page.evaluate("""(shown) => {
          let s = document.getElementById('landing-frame');
          if (!s) { s = document.createElement('style'); s.id = 'landing-frame'; document.head.append(s); }
          s.textContent = shown ? '' : 'section.gui-console, section.gui-roster { visibility: hidden; }';
        }""", shown)

    def play(self, url: str, look: str) -> None:
        page = self.page
        page.goto(url)
        page.wait_for_selector(".gui-hut", timeout=30000)
        page.evaluate("import('/static/js/link.js').then(m => { window.__ork = m; })")
        self.until("true")
        page.evaluate("id => window.__ork.command('orkspace.select', {id})", fd.ID)
        self.until("t.active_orkspace === arg", fd.ID)
        page.wait_for_selector(f'.gui-hut[data-id="{fd.POST}"]', timeout=10000)
        self.settle(look)
        self.strip(False)
        self.wait(1500)
        self.frame("front-desk", "The Front Desk: Inbox (mail and Slack), Triage, Tasks, Agents at work and "
                                 "Results")
        mail_road, chat_road = f"{fd.TRIAGE}:{fd.POST}-mail_received", f"{fd.TRIAGE}:{fd.POST}-watch_comment"
        human, agent = f"{fd.BOARD}:{fd.TRIAGE}-team_routed", f"{fd.BOARD}:{fd.TRIAGE}-team_routed-2"
        to_camp = f"{fd.CAMP}:{fd.BOARD}-tasks_sent"
        started, result = f"{fd.BOARD}:{fd.CAMP}-pool_assigned", f"{fd.BOARD}:{fd.CAMP}-pool_done"
        outcome = f"{fd.LOOT}:{fd.CAMP}-pool_done"

        # 1. a mail: triaged, then the person's
        self.simulate(fd.MAIL)
        self.cart_on(mail_road, "Thursday")
        self.wait(600)
        self.frame("mail-arrives", "A mail arrives: the Inbox shows it — Dana asks to move Thursday's review")
        self.wait(TRAVEL_S * 1000 * 0.35)
        self.frame("mail-to-triage", "It travels the road to Triage")
        self.until("t.buildings.some(b => b.id === arg && b.card && b.card.state === 'running')", fd.TRIAGE)
        self.open_card(fd.TRIAGE)
        self.until("t.buildings.some(b => b.id === arg && b.card && b.card.state === 'running' && b.card.ok >= 2)",
                   fd.TRIAGE)
        self.wait(400)
        self.frame("triage-reading", "Triage reads it: each member gives a short verdict")
        self.cart_on(human, "Dana")
        self.wait(500)
        self.frame("triage-verdicts", "The verdicts are in: stressed, medium priority, before Thursday. The steward "
                                      "decides it is yours: “Reply to Dana: move Thursday's review?”")
        self.close()
        self.wait(TRAVEL_S * 1000 * 0.2)
        self.frame("task-for-human", "It goes down the road “task for human”")
        self.until("t.buildings.some(b => b.id === arg[0] && b.card && b.card.todos && "
                   "b.card.todos.top.some(x => x.includes(arg[1])))", [fd.BOARD, "Dana"])
        self.wait(700)
        self.frame("my-todo", "…and lands in your to-dos in Tasks")
        self.open_full(fd.BOARD)
        self.frame("my-todo-board", "Your to-dos: reply to Dana — the agents' tasks stay apart, above")
        self.close()

        # 2. a Slack message: triaged, then an agent's — and done by itself
        self.simulate(fd.CHAT)
        self.cart_on(chat_road, "Feedback summary")
        self.wait(600)
        self.frame("slack-arrives", "A Slack message arrives: Sam asks for a summary of last month's feedback")
        self.until("t.buildings.some(b => b.id === arg && b.card && b.card.state === 'running')", fd.TRIAGE)
        self.open_card(fd.TRIAGE)
        self.cart_on(agent, "Summarize")
        self.wait(500)
        self.frame("triage-agent", "Triage: low risk, routine, due Friday — the steward gives it to an agent: "
                                   "“Summarize last month's feedback for the team (by Fri)”")
        self.close()
        self.wait(TRAVEL_S * 1000 * 0.2)
        self.frame("task-for-agent", "It goes down the road “task for agent”")
        self.cart_on(to_camp, "Summarize")
        self.open_card(fd.BOARD)
        self.frame("kanban-todo", "A task in the agents' To Do — Tasks sends it to the agents at once")
        self.close()
        self.frame("to-barracks", "The task travels to Agents at work")
        self.cart_on(started, "Summarize")
        self.open_card(fd.CAMP)
        self.frame("ork-working", "An agent takes it and works on it")
        self.close()
        self.until("t.buildings.some(b => b.id === arg && b.card && b.card.lanes && "
                   "b.card.lanes.some(l => l.id === 'in_progress' && l.count > 0))", fd.BOARD)
        self.open_full(fd.BOARD)
        self.frame("kanban-in-progress", "In Tasks the card moves to In Progress, with who works on it")
        self.close()
        self.cart_on(result, "Summarize")
        self.wait(TRAVEL_S * 1000 * 0.4)
        self.frame("result-back", "Done: the result goes back to Tasks and on to Results")
        self.until("t.buildings.some(b => b.id === arg && b.card && b.card.lanes && "
                   "b.card.lanes.some(l => l.id === 'done' && l.count > 1))", fd.BOARD)
        self.wait(TRAVEL_S * 1000 * 0.2)
        self.open_full(fd.BOARD)
        self.frame("kanban-done", "The card lands in Done with the result: the summary is shared, ticket #142")
        self.close()
        self.cart_on(outcome, "Summarize")
        self.until("t.buildings.some(b => b.id === arg && b.card && b.card.passed > 0)", fd.LOOT)
        self.open_card(fd.LOOT)
        self.frame("loot-outcome", "Results: “Feedback summary shared with the team”, ticket #142, with its links")
        self.close()
        self.wait(1500)
        self.frame("all-done", "Both handled: “Reply to Dana” waits in your to-dos, the agent's task is Done "
                               "and its outcome is in Results")


def to_mp4(webm: Path, mp4: Path) -> Path:
    found = shutil.which("ffmpeg") or next((str(p) for p in Path("/opt/pw-browsers").glob("ffmpeg-*/ffmpeg*")), "")
    if not found:
        return webm
    probe = subprocess.run([found, "-y", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags",
                            "+faststart", str(mp4)], capture_output=True, text=True)
    if probe.returncode == 0 and mp4.is_file():
        return mp4
    return webm


def film(look: str, out: Path, chromium: str) -> dict:
    from playwright.sync_api import sync_playwright

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    demo_dir = Path(tempfile.mkdtemp(prefix="orkcraft-landing-")) / "demo"
    proc, url = start_gui(demo_dir, free_port(), out / "gui.log", look)
    videos = out / "video-raw"
    raw = None
    try:
        with sync_playwright() as p:
            browser = launch(p, chromium)
            ctx = browser.new_context(viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]}, device_scale_factor=SCALE,
                                      record_video_dir=str(videos),
                                      record_video_size={"width": VIEWPORT[0], "height": VIEWPORT[1]})
            page = ctx.new_page()
            f = Film(page, out)
            try:
                f.play(url, look)
            finally:
                video = page.video
                ctx.close()                               # the video is written when its page closes
                raw = video.path() if video else None
                browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
    webm = Path(raw) if raw else None
    made = ""
    if webm and webm.is_file():
        kept = out / f"landing-flow-{look}.webm"
        shutil.move(str(webm), kept)
        made = str(to_mp4(kept, kept.with_suffix(".mp4")))
        if made.endswith(".mp4"):
            kept.unlink()
    shutil.rmtree(videos, ignore_errors=True)
    shutil.rmtree(demo_dir.parent, ignore_errors=True)
    report = {"look": look, "frames": f.captions, "video": Path(made).name if made else "", "problems": f.problems}
    (out / "frames.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "landing-flow", help="where the frames and the video go")
    ap.add_argument("--mode", choices=("camp", "office"), default=None, help="one look only (default: both)")
    ap.add_argument("--chromium", default=os.environ.get("ORKCRAFT_CHROMIUM", ""),
                    help="a Chromium to drive (default: Playwright's own)")
    args = ap.parse_args(argv)
    for look in ([args.mode] if args.mode else ["camp", "office"]):
        print(f"{look}:", flush=True)
        r = film(look, args.out.resolve() / look, args.chromium)
        print(f"  video: {r['video'] or 'none'}; problems: {len(r['problems'])}", flush=True)
        for p in r["problems"]:
            print(f"  ! {p}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
