"""The orc's chat: the tall right column of the console when an orc is selected.

Instead of a menu of commands: the orc's live session (its terminal mirrored here, the line
below types into it), or — when nothing runs — its last runs and a line that starts a session
with its orders; below, the earlier sessions of this orc, Enter reopens one. The commands stay
on their keys (D, H, W, T) and in one line at the bottom.
"""
from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm.orcs import RESIDENT, WORKER, Orc

HISTORY_ROWS = 5
MIRROR_LINES = 200


class OrcChat(Vertical):
    DEFAULT_CSS = """
    OrcChat {
        position: absolute;
        layer: overlay;
        border: round $accent;
        background: $background;
        padding: 0 1;
    }
    OrcChat #orc-chat-title { height: 1; text-style: bold; color: $accent; }
    OrcChat #orc-chat-scroll { height: 1fr; background: transparent; }
    OrcChat #orc-chat-history-title { height: 1; color: $text-muted; }
    OrcChat #orc-chat-history { height: auto; max-height: 5; background: transparent; border: none; padding: 0; }
    OrcChat #orc-chat-input { height: 3; }
    OrcChat #orc-chat-footer { height: 1; color: $text-muted; }
    """

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self.orc_key: str | None = None
        self._sessions: list = []
        self._signature: tuple = ()

    def compose(self) -> ComposeResult:
        yield Static("", id="orc-chat-title", markup=False)
        with VerticalScroll(id="orc-chat-scroll"):
            yield Static("", id="orc-chat-log", markup=False)
        yield Static("Earlier sessions — Enter reopens", id="orc-chat-history-title", markup=False)
        yield OptionList(id="orc-chat-history")
        yield Input(id="orc-chat-input")
        yield Static("Enter sends · / types here · D dismiss · H halt · T orders · W watch · Esc back",
                     id="orc-chat-footer", markup=False)

    # -- what the orc is ------------------------------------------------------------------------

    def _orc(self) -> Orc | None:
        from orkcraft.screens.console import orc_key
        return next((o for o in self.app.roster.orcs if orc_key(o) == self.orc_key), None)

    def _terminal(self, orc: Orc):
        key = orc.session if orc.category == RESIDENT else (orc.ref if orc.category == WORKER else "")
        term = getattr(self.app.chat, "terminals", {}).get(key) if key else None
        return term if term is not None and term.running else None

    @staticmethod
    def supports(orc: Orc | None) -> bool:
        return orc is not None and orc.category in (RESIDENT, WORKER)

    # -- render ---------------------------------------------------------------------------------

    def show_orc(self, key: str | None) -> None:
        if key != self.orc_key:
            self.orc_key = key
            self._signature = ()
            self._load_history()
            self.query_one("#orc-chat-input", Input).value = ""
        self.refresh_chat()

    def _load_history(self) -> None:
        from orkcraft.sources.sessions import collect_sessions, sessions_for_orc

        orc = self._orc()
        lst = self.query_one("#orc-chat-history", OptionList)
        lst.clear_options()
        self._sessions = []
        if orc is not None and orc.category == RESIDENT and orc.ref:
            try:
                self._sessions = sessions_for_orc(collect_sessions(self.app.repo_root), orc.ref)[:HISTORY_ROWS * 4]
            except OSError:
                self._sessions = []
        for i, s in enumerate(self._sessions):
            when = s.last.strftime("%m-%d %H:%M") if s.last else "—"
            lst.add_option(Option(Text(f"{when}  {s.harness}  {s.title or s.id[:8]}", no_wrap=True,
                                       overflow="ellipsis"), id=str(i)))
        if not self._sessions:
            lst.add_option(Option(Text("none yet", style="dim"), disabled=True))

    def refresh_chat(self) -> None:
        """Called on show and by the app's timer while the chat is visible."""
        if not self.is_attached:
            return
        orc = self._orc()
        title = self.query_one("#orc-chat-title", Static)
        log = self.query_one("#orc-chat-log", Static)
        line = self.query_one("#orc-chat-input", Input)
        if orc is None:
            title.update("💬 —")
            log.update(Text("This ork is gone.", style="dim"))
            return
        term = self._terminal(orc)
        if term is not None:
            lines = [ln.rstrip() for ln in term.text_lines()][-MIRROR_LINES:]
            while lines and not lines[-1]:
                lines.pop()
            sig = ("term", len(lines), lines[-1] if lines else "")
            title.update(f"💬 {orc.name} · live session")
            line.placeholder = "type to the session, Enter sends"
            if sig != self._signature:
                self._signature = sig
                log.update(Text("\n".join(lines) or "(the session has not printed anything yet)"))
                self.query_one("#orc-chat-scroll", VerticalScroll).scroll_end(animate=False)
            return
        sig = ("runs", orc.status, len(getattr(self.app.roads, "runs", [])))
        title.update(f"💬 {orc.name} · no live session")
        line.placeholder = ("message → a new session with its orders, Enter starts it"
                            if orc.category == RESIDENT and not orc.lead else "nothing to type to")
        if sig != self._signature:
            self._signature = sig
            log.update(self._past(orc))

    def _past(self, orc: Orc) -> Text:
        """Its last runs (a handler), its last report (a steward), or how to start."""
        t = Text()
        if orc.category == RESIDENT and orc.lead and orc.building:
            from orkcraft.realm import steward
            report = steward.load_report(self.app.repo_root, orc.building)
            if report:
                t.append(f"Last watch {report.get('ts', '')[:16].replace('T', ' ')}\n", style="bold")
                for f in report.get("findings", [])[:6]:
                    t.append(f"• {f.get('kind', '')}: {f.get('detail', f.get('text', ''))}\n")
                for p in report.get("proposals", [])[:3]:
                    t.append(f"→ {p.get('type', '')} {p.get('orc', '')}: {p.get('why', '')}\n", style="cyan")
            else:
                t.append("Not watched yet — W watches now.", style="dim")
            return t
        ref_orc = orc.ref.split("/", 1)[1] if "/" in orc.ref else ""
        runs = [r for r in getattr(self.app.roads, "runs", []) if r.target == orc.building and r.orc_id == ref_orc]
        for r in runs[-6:][::-1]:
            first = next((ln for ln in r.markdown.splitlines() if ln.strip()), "") or r.error
            t.append(f"{r.outcome:<11}", style="green" if r.outcome == "done" else "yellow")
            t.append(f" {first[:160]}\n")
        if not runs:
            t.append("No runs in this session yet. ", style="dim")
            t.append("Type below to start a Claude session with its orders"
                     if orc.category == RESIDENT and not orc.lead else "", style="dim")
        return t

    # -- input ----------------------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        text = event.value.strip()
        event.input.value = ""
        orc = self._orc()
        if not text or orc is None:
            return
        term = self._terminal(orc)
        if term is not None:
            term.write((text + "\r").encode())
        elif orc.category == RESIDENT and not orc.lead:
            self.app.deploy_resident(orc, first_message=text, show_tent=False)
        self._signature = ()
        self.call_after_refresh(self.refresh_chat)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        orc = self._orc()
        if orc is None or not (event.option_id or "").isdigit():
            return
        session = self._sessions[int(event.option_id)]
        self.app.resume_for_orc(orc, session)
        self._signature = ()

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.app.action_escape()
            event.stop()
