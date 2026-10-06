"""Film whole flows of the product for its landing page, step by step through the real road engine.

    python tools/landing_flow.py [--flow desk|meeting|all] [--out DIR] [--mode camp|office] [--chromium PATH]

It builds the demo afresh, starts `orkcraft gui --demo --browser` (carts slowed down so each one is
seen on its road) and opens the flow's orkspace. Then it plays the flow through the real road engine
— the Watchtower hears each message as its source would send it (the sandbox's `simulate` act), and
every cart after that is the town's own. Two flows:

desk (default; the Front Desk, demo/front_desk.py) — a mail and a Slack message, triaged:
    a mail arrives in the Inbox (a Watchtower) → Triage (a Clan Fire that routes): each member's
      verdict, the steward's route → "task for human" → one of the person's to-dos in Tasks (Task Fields)
    a Slack message arrives → Triage → "task for agent" → a task in To Do, which Tasks sends to
      Agents at work (a Barracks) → an ork works it (In Progress) → the result comes back (Done) and
      goes on to Results (a Loot Vault) with its links

meeting (Meetings, demo/meetings.py) — a mail that asks to meet, and the brief for the meeting:
    Alex's mail arrives in the Inbox → Triage: a risk analyst, a tone reader and a productivity pulse,
      the steward says it is a meeting, tomorrow 11:00 → "new meeting" → the Calendar (a War Drum) adds
      the event and asks for its brief → "prepare" → Agents at work, which read Notes (a Scroll Dump)
      first: the task comes back "with the notes" → an ork writes the brief → Results, and back to the
      Calendar, where the event wears its document

At each step it takes a frame (1440×900 at twice the pixels, PNG) and the whole flow is recorded as
a video (mp4 when ffmpeg is found, else webm), into OUT/<flow>/<look>. Without --mode it films both
looks (camp and office). Needs Playwright and a Chromium (tools/gallery.py says how).
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
from orkcraft.demo import meetings as mt  # noqa: E402

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

    def simulate(self, message: dict, post: str = fd.POST) -> None:
        self.page.evaluate("([id, args]) => window.__ork.act(id, 'simulate', args)", [post, message])

    def has(self, bid: str, js: str, arg=None, timeout: float = 60_000) -> None:
        """Wait till the card of building `bid` (`c`) makes `js` true."""
        self.until(f"t.buildings.some(b => b.id === arg[0] && b.card && ((c, arg) => {js})(b.card, arg[1]))",
                   [bid, arg], timeout)

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
        """The film frames a building's Command Card alone: Info and its orks below it say nothing new here;
        nor do the War Map, the status bar and the toasts (what they would say, the frames show)."""
        self.page.evaluate("""(shown) => {
          let s = document.getElementById('landing-frame');
          if (!s) { s = document.createElement('style'); s.id = 'landing-frame'; document.head.append(s); }
          s.textContent = shown ? '' : 'section.gui-console, section.gui-roster, .gui-warmap, .gui-status, '
            + '.gui-toasts { visibility: hidden; }';
        }""", shown)

    def enter(self, url: str, look: str, orkspace: str, first: str) -> None:
        """The GUI, the orkspace chosen, the other orkspaces' questions answered, the frame cleared."""
        page = self.page
        page.goto(url)
        page.wait_for_selector(".gui-hut", timeout=30000)
        page.evaluate("import('/static/js/link.js').then(m => { window.__ork = m; })")
        self.until("true")
        page.evaluate("id => window.__ork.command('orkspace.select', {id})", orkspace)
        self.until("t.active_orkspace === arg", orkspace)
        page.wait_for_selector(f'.gui-hut[data-id="{first}"]', timeout=10000)
        self.settle(look)
        self.strip(False)
        self.wait(1500)

    def play_desk(self, url: str, look: str) -> None:
        self.enter(url, look, fd.ID, fd.POST)
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
        self.cart_on(result, "shared with the team")
        self.wait(TRAVEL_S * 1000 * 0.4)
        self.frame("result-back", "Done: the result goes back to Tasks and on to Results")
        self.until("t.buildings.some(b => b.id === arg && b.card && b.card.lanes && "
                   "b.card.lanes.some(l => l.id === 'done' && l.count > 1))", fd.BOARD)
        self.wait(TRAVEL_S * 1000 * 0.2)
        self.open_full(fd.BOARD)
        self.frame("kanban-done", "The card lands in Done with the result: the summary is shared, ticket #142")
        self.close()
        self.cart_on(outcome, "shared with the team")
        self.until("t.buildings.some(b => b.id === arg && b.card && b.card.passed > 0)", fd.LOOT)
        self.open_card(fd.LOOT)
        self.frame("loot-outcome", "Results: “Feedback summary shared with the team”, ticket #142, with its links")
        self.close()
        self.wait(1500)
        self.frame("all-done", "Both handled: “Reply to Dana” waits in your to-dos, the agent's task is Done "
                               "and its outcome is in Results")

    def play_meeting(self, url: str, look: str) -> None:
        """Meetings (demo/meetings.py): Alex's mail becomes an event, and the event gets its brief."""
        self.enter(url, look, mt.ID, mt.POST)
        self.frame("meetings", "Meetings: Inbox, Triage and Calendar on top; Notes, Agents at work and Results "
                               "below")
        mail = f"{mt.TRIAGE}:{mt.POST}-mail_received"
        new_meeting = f"{mt.DRUM}:{mt.TRIAGE}-team_routed"
        prepare = f"{mt.CAMP}:{mt.DRUM}-calendar_event_upcoming"
        with_notes = f"{mt.CAMP}:{mt.NOTES}-knowledge_chunks"
        brief_back, brief_out = f"{mt.DRUM}:{mt.CAMP}-pool_done", f"{mt.LOOT}:{mt.CAMP}-pool_done"

        # 1. the mail
        self.simulate(mt.MAIL, mt.POST)
        self.cart_on(mail, "new project")
        self.wait(600)
        self.frame("mail-arrives", "A mail arrives in the Inbox: Alex asks to meet tomorrow about the new project")
        self.wait(TRAVEL_S * 1000 * 0.35)
        self.frame("mail-to-triage", "It travels the road to Triage")

        # 2. triage
        self.has(mt.TRIAGE, "c.state === 'running'")
        self.open_card(mt.TRIAGE)
        self.has(mt.TRIAGE, "c.state === 'running' && c.ok >= 2")
        self.wait(400)
        self.frame("triage-reading", "Triage reads it: the risk, the tone, and how full tomorrow is")
        self.cart_on(new_meeting, "kickoff")
        self.wait(500)
        self.frame("triage-decides", "Tomorrow is free at 11:00, so the steward decides: a meeting, "
                                     "“New project kickoff with Alex”, tomorrow 11:00 for 30 min")
        self.close()

        # 3. the calendar
        self.wait(TRAVEL_S * 1000 * 0.3)
        self.frame("new-meeting-road", "It goes down the road “new meeting” to the Calendar")
        self.has(mt.DRUM, "c.beats.some(x => x.title.includes(arg))", "kickoff")
        self.wait(250)
        self.frame("calendar-event", "The Calendar adds the event: tomorrow 11:00, New project kickoff with Alex")

        # 4. the calendar asks for a brief at once
        self.cart_on(prepare, "kickoff")
        self.wait(TRAVEL_S * 1000 * 0.05)
        self.frame("prepare-road", "The Calendar asks for a brief for the meeting: “prepare” goes to Agents at work")

        # 5. the agent reads the notes, then writes
        self.has(mt.NOTES, "!!c.lent")
        self.cart_on(with_notes, "kickoff")
        self.wait(TRAVEL_S * 1000 * 0.45)
        self.frame("notes-read", "Agents at work read the project's notes first: its goals, the decisions so far, "
                                 "the open questions")
        self.has(mt.CAMP, "c.active > 0")
        self.open_card(mt.CAMP)
        self.frame("agent-writes", "An agent writes the brief from the notes")
        self.close()

        # 6. the brief: in Results, and back on the event
        self.cart_on(brief_out, "kickoff")
        self.cart_on(brief_back, "kickoff")
        self.wait(TRAVEL_S * 1000 * 0.45)
        self.frame("brief-travels", "The brief is ready: it goes to Results, and back to the Calendar")
        self.has(mt.LOOT, "c.passed > 0")
        self.has(mt.DRUM, "c.beats.some(x => x.doc)")
        self.wait(600)
        self.open_card(mt.LOOT)
        self.frame("results", "Results: “Brief ready: New project kickoff”, with its link")
        self.open_card(mt.DRUM)
        self.page.locator("section.gui-card .gui-drum__beat.is-meeting", has_text="kickoff").first.click()
        self.wait(600)
        self.frame("calendar-doc", "In the Calendar the meeting now has its brief: the doc mark opens it")
        self.page.locator("section.gui-card button.ok-chip", has_text="doc").first.click()
        self.page.wait_for_selector(".gui-lake, .gui-lake-window, [class*=lake]", timeout=10000)
        self.wait(1500)
        self.frame("brief-open", "The brief: where the project is, what is decided, what is open, an agenda")
        self.page.locator(".gui-lake__tab .gui-tab__close").first.click()
        self.close()
        self.wait(1500)
        self.frame("all-done", "Done: the meeting is in the calendar with its brief, and the brief is in Results")



def to_mp4(webm: Path, mp4: Path) -> Path:
    found = shutil.which("ffmpeg") or next((str(p) for p in Path("/opt/pw-browsers").glob("ffmpeg-*/ffmpeg*")), "")
    if not found:
        return webm
    probe = subprocess.run([found, "-y", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags",
                            "+faststart", str(mp4)], capture_output=True, text=True)
    if probe.returncode == 0 and mp4.is_file():
        return mp4
    return webm


FLOWS = ("desk", "meeting")


def film(look: str, out: Path, chromium: str, flow: str = "desk") -> dict:
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
                getattr(f, f"play_{flow}")(url, look)
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
        kept = out / f"landing-flow-{flow}-{look}.webm"
        shutil.move(str(webm), kept)
        made = str(to_mp4(kept, kept.with_suffix(".mp4")))
        if made.endswith(".mp4"):
            kept.unlink()
    shutil.rmtree(videos, ignore_errors=True)
    shutil.rmtree(demo_dir.parent, ignore_errors=True)
    report = {"flow": flow, "look": look, "frames": f.captions, "video": Path(made).name if made else "", "problems": f.problems}
    (out / "frames.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "landing-flow", help="where the frames and the video go")
    ap.add_argument("--mode", choices=("camp", "office"), default=None, help="one look only (default: both)")
    ap.add_argument("--chromium", default=os.environ.get("ORKCRAFT_CHROMIUM", ""),
                    help="a Chromium to drive (default: Playwright's own)")
    ap.add_argument("--flow", choices=(*FLOWS, "all"), default="desk",
                    help="which flow: desk (the Front Desk), meeting (Meetings) or all (default: desk)")
    args = ap.parse_args(argv)
    for flow in (FLOWS if args.flow == "all" else (args.flow,)):
        for look in ([args.mode] if args.mode else ["camp", "office"]):
            print(f"{flow} · {look}:", flush=True)
            r = film(look, args.out.resolve() / flow / look, args.chromium, flow)
            print(f"  video: {r['video'] or 'none'}; problems: {len(r['problems'])}", flush=True)
            for p in r["problems"]:
                print(f"  ! {p}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
