"""Chronicles overlays: Building Chronicles (event log) and Unit Chronicles (runs & ReAct protocol)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft import scroll as ts
from orkcraft.sources.telemetry import fmt_tokens
from orkcraft.realm import chronicles, pipes
from orkcraft.realm.orcs import Orc, RESIDENT, WORKER
from orkcraft.sources import transcripts
from orkcraft.sources.sessions import HARNESS_CLAUDE, Session, collect_sessions, sessions_for_orc


class BuildingChronicles(ModalScreen[None]):
    """Building Chronicles overlay: audit log of building mutations."""

    DEFAULT_CSS = """
    BuildingChronicles {
        align: center middle;
    }
    #building-chronicles-dialog {
        width: 80;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #building-chronicles-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }
    #building-chronicles-list {
        height: auto;
        max-height: 20;
        background: transparent;
        border: none;
    }
    #building-chronicles-empty {
        padding: 1 0;
        color: $text-muted;
    }
    #building-chronicles-footer {
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close"),
        Binding("q", "dismiss(None)", "Close"),
    ]

    def __init__(self, repo_root: Path, scroll: ts.TownScroll | None, building_id: str) -> None:
        super().__init__()
        self.repo_root = repo_root
        self.scroll = scroll
        self.building_id = building_id

    def _title_text(self) -> str:
        b_spec = self.scroll.building(self.building_id) if self.scroll is not None else None
        icon = b_spec.icon if b_spec and b_spec.icon else "🏛️"
        title = b_spec.title if b_spec and b_spec.title else self.building_id
        return f"📜 CHRONICLES · {icon} {title}"

    def compose(self) -> ComposeResult:
        with Vertical(id="building-chronicles-dialog"):
            yield Static(self._title_text(), id="building-chronicles-title", markup=False)
            yield OptionList(id="building-chronicles-list")
            yield Static(
                "No events yet — actions on this building are recorded here.",
                id="building-chronicles-empty",
                markup=False,
            )
            yield Static("[Esc / q] Close", id="building-chronicles-footer", markup=False)

    def on_mount(self) -> None:
        lst = self.query_one("#building-chronicles-list", OptionList)
        empty = self.query_one("#building-chronicles-empty", Static)
        events = chronicles.history(self.repo_root, self.building_id)

        if not events:
            lst.display = False
            empty.display = True
            lst.add_option(
                Option(
                    Text("No events yet — actions on this building are recorded here.", style="dim"),
                    disabled=True,
                )
            )
        else:
            lst.display = True
            empty.display = False
            last_date: str | None = None
            for ev in events:
                ts_str = str(ev.get("ts", ""))
                date_str, time_str = self._format_ts(ts_str)
                if date_str != last_date:
                    last_date = date_str
                    lst.add_option(Option(Text(f"── {date_str} ──", style="dim bold"), disabled=True))
                icon, sentence = chronicles.describe(ev)
                by = str(ev.get("by", "operator"))
                line = f"{time_str}  {icon} {sentence}  · {by}"
                lst.add_option(Option(Text(line)))

            first_enabled = next(
                (i for i in range(lst.option_count) if not lst.get_option_at_index(i).disabled),
                0,
            )
            lst.highlighted = first_enabled
            lst.focus()

    def _format_ts(self, ts_str: str) -> tuple[str, str]:
        if not ts_str:
            return "—", "—"
        try:
            val = dt.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return val.strftime("%Y-%m-%d"), val.strftime("%H:%M:%S")
        except ValueError:
            if "T" in ts_str:
                d, rest = ts_str.split("T", 1)
                return d, rest[:8]
            return "—", ts_str[:8]


class UnitChronicles(ModalScreen[None]):
    """Unit Chronicles overlay: runs on the left (40%), protocol on the right (60%)."""

    DEFAULT_CSS = """
    UnitChronicles {
        align: center middle;
    }
    #unit-chronicles-dialog {
        width: 100;
        max-width: 95%;
        height: 32;
        max-height: 90%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #unit-chronicles-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }
    #unit-chronicles-cols {
        height: 1fr;
        width: 100%;
    }
    #runs-col {
        width: 40%;
        height: 100%;
        border-right: solid $surface-lighten-2;
        padding-right: 1;
    }
    #protocol-col {
        width: 60%;
        height: 100%;
        padding-left: 1;
    }
    #runs-list {
        height: 1fr;
        background: transparent;
        border: none;
    }
    #runs-empty {
        padding: 1 0;
        color: $text-muted;
    }
    #protocol-steps {
        height: 12;
        max-height: 12;
        background: transparent;
        border: none;
    }
    #protocol-empty {
        padding: 1 0;
        color: $text-muted;
    }
    #step-detail-scroll {
        height: 1fr;
        border-top: solid $surface-lighten-2;
        margin-top: 1;
    }
    #step-detail {
        color: $text;
    }
    #unit-chronicles-footer {
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close"),
        Binding("q", "dismiss(None)", "Close"),
        Binding("d", "show_diff", "Diff to Spire"),
        Binding("D", "show_diff", "Diff to Spire", show=False),
        Binding("r", "resume_run", "Resume"),
        Binding("R", "resume_run", "Resume", show=False),
        Binding("left", "focus_left", "Runs", show=False),
        Binding("h", "focus_left", "Runs", show=False),
        Binding("right", "focus_right", "Protocol", show=False),
        Binding("l", "focus_right", "Protocol", show=False),
    ]

    def __init__(self, orc: Orc, repo_root: Path, tool: str | None = None) -> None:
        """`tool`: only the runs that used this tool, and only its calls in their protocol."""
        super().__init__()
        self.orc = orc
        self.repo_root = repo_root
        self.tool = tool
        self._runs_cache: dict[str, transcripts.Run] = {}
        self.sessions: list[Session] = []
        self._session_numbers: dict[str, str] = {}
        self._current_session: Session | None = None
        self._current_run: transcripts.Run | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="unit-chronicles-dialog"):
            tool = f" · 🔧 {self.tool}" if self.tool else ""
            yield Static(
                f"📜 UNIT CHRONICLES · 🧌 {self.orc.name} ({self.orc.role}){tool}",
                id="unit-chronicles-title",
                markup=False,
            )
            with Horizontal(id="unit-chronicles-cols"):
                with Vertical(id="runs-col"):
                    yield OptionList(id="runs-list")
                    yield Static(
                        "No runs yet — deploy this ork (C) to start one.",
                        id="runs-empty",
                        markup=False,
                    )
                with Vertical(id="protocol-col"):
                    yield OptionList(id="protocol-steps")
                    yield Static(
                        "Protocol not available for this session.",
                        id="protocol-empty",
                        markup=False,
                    )
                    with VerticalScroll(id="step-detail-scroll"):
                        yield Static("", id="step-detail", markup=False)
            yield Static(
                "[Enter] Expand step   [D] Diff to Spire   [R] Resume in War Tent   [Esc / q] Close",
                id="unit-chronicles-footer",
                markup=False,
            )

    def on_mount(self) -> None:
        runs_list = self.query_one("#runs-list", OptionList)
        runs_empty = self.query_one("#runs-empty", Static)
        proto_list = self.query_one("#protocol-steps", OptionList)
        proto_empty = self.query_one("#protocol-empty", Static)
        detail = self.query_one("#step-detail", Static)

        all_sessions = collect_sessions(self.repo_root)
        if self.orc.category == RESIDENT:
            raw_sessions = sessions_for_orc(all_sessions, self.orc.ref)
        elif self.orc.category == WORKER:
            s = next((x for x in all_sessions if x.key == self.orc.ref), None)
            raw_sessions = [s] if s else []
        else:
            raw_sessions = []

        if self.tool:
            raw_sessions = [s for s in raw_sessions if self._uses_tool(s)]

        if not raw_sessions:
            self.sessions = []
            runs_list.display = False
            runs_empty.display = True
            runs_list.add_option(
                Option(Text("No runs yet — deploy this ork (C) to start one.", style="dim"), disabled=True)
            )
            proto_list.display = False
            proto_empty.display = True
            detail.update("")
            return

        chrono = sorted(raw_sessions, key=lambda s: s.started or s.last or dt.datetime.min)
        self._session_numbers = {s.key: f"#{i+1:03d}" for i, s in enumerate(chrono)}

        self.sessions = list(reversed(chrono))
        runs_list.display = True
        runs_empty.display = False
        runs_list.clear_options()

        for s in self.sessions:
            label = self._format_run_label(s)
            runs_list.add_option(Option(label, id=s.key))

        runs_list.highlighted = 0
        runs_list.focus()
        self._select_session(self.sessions[0])

    def _uses_tool(self, session: Session) -> bool:
        run = self._get_run(session)
        return run is not None and any(st.tool == self.tool for st in run.steps)

    def _get_run(self, session: Session) -> transcripts.Run | None:
        if session.harness != HARNESS_CLAUDE or not session.transcript:     # only Claude's transcripts are read
            return None
        t_path = session.transcript
        if t_path not in self._runs_cache:
            self._runs_cache[t_path] = transcripts.read_run(t_path)
        return self._runs_cache[t_path]

    def _format_run_label(self, session: Session) -> Text:
        num = self._session_numbers.get(session.key, "#001")
        run = self._get_run(session)

        when = run.started if run and run.started else (session.started or session.last)
        if when:
            date_str = when.strftime("%d %b %H:%M")
        else:
            date_str = "—"

        if run and run.duration_s is not None:
            dur = int(run.duration_s)
            m, s = divmod(dur, 60)
            h, m = divmod(m, 60)
            if h > 0:
                dur_str = f"{h}h {m:02d}m"
            else:
                dur_str = f"{m}m {s:02d}s"
        else:
            dur_str = "—"

        tok_str = f"🪵 {fmt_tokens(run.context_tokens)}" if run and run.context_tokens else "🪵 —"
        cost = run.cost if run else None
        if cost is None:
            gold_str = "🪙 ?" if run and run.unpriced else "🪙 —"
        else:
            # "+" when part of the run used a model with no published price.
            gold_str = f"🪙 ${cost:.2f}{'+' if run.unpriced else ''}"
        outcome_str = run.outcome if run else "…"

        text = f"{num} · {date_str} · {dur_str} · {tok_str} · {gold_str} · {outcome_str}"
        return Text(text)

    def _select_session(self, session: Session) -> None:
        self._current_session = session
        proto_list = self.query_one("#protocol-steps", OptionList)
        proto_empty = self.query_one("#protocol-empty", Static)
        detail = self.query_one("#step-detail", Static)
        detail.update("")

        run = self._get_run(session)
        self._current_run = run

        if run is None or (run.error and not run.steps):
            proto_list.display = False
            proto_empty.display = True
            proto_list.clear_options()
            return

        proto_list.display = True
        proto_empty.display = False
        proto_list.clear_options()

        for idx, step in enumerate(run.steps):
            if self.tool and step.tool != self.tool:
                continue
            proto_list.add_option(Option(Text(step.title), id=str(idx)))

        if run.truncated:
            proto_list.add_option(Option(Text("… transcript cut at 20 MB", style="dim italic"), disabled=True))

        if run.steps:
            proto_list.highlighted = 0

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "runs-list":
            if event.option_id:
                s = next((x for x in self.sessions if x.key == event.option_id), None)
                if s is not None and s != self._current_session:
                    self._select_session(s)
        event.stop()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "protocol-steps":
            idx = int(event.option_id) if (event.option_id or "").isdigit() else -1
            if self._current_run:
                if 0 <= idx < len(self._current_run.steps):
                    step = self._current_run.steps[idx]
                    self.query_one("#step-detail", Static).update(step.detail)
        elif event.option_list.id == "runs-list":
            proto = self.query_one("#protocol-steps", OptionList)
            if proto.display:
                proto.focus()
        event.stop()

    def action_focus_left(self) -> None:
        self.query_one("#runs-list", OptionList).focus()

    def action_focus_right(self) -> None:
        p = self.query_one("#protocol-steps", OptionList)
        if p.display:
            p.focus()

    def action_show_diff(self) -> None:
        run = self._current_run
        if not run or not run.diffs:
            self.app.notify("no file changes in this run", title="Diff")
            return
        diff_texts = [s.diff for s in run.diffs if s.diff]
        if not diff_texts:
            self.app.notify("no file changes in this run", title="Diff")
            return
        body = "\n\n".join(diff_texts)
        markdown = f"```diff\n{body}\n```"
        source = self.orc.building or "forge"
        title = f"Diff · {self.orc.name}"
        payload = pipes.Payload(kind=pipes.TEXT, value=markdown, source=source, mode=pipes.ON_TASK, title=title)
        if hasattr(self.app, "preview"):
            self.app.preview.show_payload(payload, title, markdown)

    def action_resume_run(self) -> None:
        session = self._current_session
        if session is None:
            return
        app = self.app
        if hasattr(app, "scroll") and app.scroll is not None and hasattr(app, "roster"):
            if app.roster.active >= app.scroll.budget.supply_max_workers:
                app.notify(
                    f"🥩 Supply {app.roster.active}/{app.scroll.budget.supply_max_workers}: build more farms first "
                    "(stop a session with x in the War Tent)",
                    title="Not enough food",
                    severity="warning",
                )
                return
            if hasattr(app, "gold_exhausted") and app.gold_exhausted():
                return
        self.dismiss(None)
        if hasattr(app, "open_session"):
            app.open_session(session)
