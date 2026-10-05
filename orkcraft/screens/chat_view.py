"""Chat window: sessions of the selected node on the left, a live Claude / agy / Codex terminal on the right.

The terminal is the real CLI on a PTY, so its own interface — polls, buttons,
`/model`, `/goal`, permission prompts — works unchanged. Started sessions keep
running in the background when you switch to another one.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import ContentSwitcher, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.sources.sessions import (
    HARNESS_AGY, HARNESS_CLAUDE, HARNESS_CLAUDE_WEB, HARNESS_CODEX, Session, collect_sessions, new_command,
    resume_command, sessions_for,
)
from orkcraft.widgets.terminal import Terminal

HARNESS_ICONS = {HARNESS_CLAUDE: "✳", HARNESS_AGY: "◆", HARNESS_CODEX: "⌬", HARNESS_CLAUDE_WEB: "☁"}
HARNESS_STYLES = {HARNESS_AGY: "bold blue", HARNESS_CODEX: "bold #10a37f"}


def session_label(s: Session, running: bool = False) -> Text:
    t = Text(no_wrap=True, overflow="ellipsis")
    t.append("▶ " if running else "  ", style="bold green")
    t.append(f"{HARNESS_ICONS.get(s.harness, '·')} ", style=HARNESS_STYLES.get(s.harness, "bold magenta"))
    when = s.last.strftime("%d.%m %H:%M") if s.last else "—"
    t.append(f"{when} ", style="cyan")
    if s.tickets:
        t.append(" ".join(sorted(s.tickets)[:3]) + " ", style="bold")
    t.append(s.title or s.short_id, style="" if s.resumable else "dim")
    return t


class ChatView(Container):
    """Enter resumes the highlighted session here; F12 leaves the terminal."""

    BINDINGS = [
        Binding("n", "new_session('claude')", "New Claude"),
        Binding("a", "new_session('agy')", "New agy"),
        Binding("c", "new_session('codex')", "New Codex"),
        Binding("A", "toggle_scope", "All / Node"),
        Binding("x", "stop_session", "Stop"),
        Binding("f12", "focus_list", "Leave Terminal", show=False),
    ]

    DEFAULT_CSS = """
    ChatView {
        height: 100%;
        width: 100%;
    }
    ChatView > Horizontal {
        height: 100%;
    }
    #chat-side {
        width: 38;
        min-width: 24;
        height: 100%;
        border-right: solid $surface-lighten-2;
    }
    #chat-scope {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    #chat-sessions {
        height: 1fr;
        background: transparent;
        border: none;
    }
    #chat-help {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    #chat-main {
        width: 1fr;
        height: 100%;
    }
    #chat-placeholder {
        padding: 1 2;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)
        self.node_id: str | None = None
        self.all_scope = False
        self.sessions: list[Session] = []
        self.shown: list[Session] = []
        self.terminals: dict[str, Terminal] = {}  # session key (or "new:…") → terminal
        self.meta: dict[str, tuple[str, str, str | None]] = {}  # key → (harness, title, ticket)
        self._new_count = 0
        self._deploy_count = 0
        self._term_seq = 0

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="chat-side"):
                yield Static("", id="chat-scope")
                yield OptionList(id="chat-sessions")
                yield Static(
                    Text("enter resume · n new Claude · a new agy · c new Codex\nA all/node · x stop · F12 leave terminal",
                         style="dim"),
                    id="chat-help",
                )
            with ContentSwitcher(id="chat-main", initial="chat-placeholder"):
                yield Static(
                    Text("Pick a session and press Enter, or n / a / c to start one.\n"
                         "The node selected in any window scopes the list (A shows all).", style="dim"),
                    id="chat-placeholder",
                )

    def on_mount(self) -> None:
        self.refresh_view()

    # -- sessions list ---------------------------------------------------------------------

    def set_node(self, node_id: str | None) -> None:
        if node_id != self.node_id:
            self.node_id = node_id
            self._render_list()

    def mini_status(self) -> list[str]:
        """Hut lines: live sessions and the newest one."""
        live = list(self.meta.values())
        return [f"⚙ {len(self.terminals)} live · {len(self.sessions)} past",
                f"{live[-1][0]} · {live[-1][1]}" if live else "no live session"]

    def refresh_view(self) -> None:
        self.sessions = collect_sessions(self.app.repo_root, max_age=0)  # type: ignore[attr-defined]
        self._render_list()

    def _render_list(self) -> None:
        scoped = not self.all_scope and self.node_id
        self.shown = sessions_for(self.sessions, self.node_id) if scoped else list(self.sessions)
        scope = Text()
        scope.append(f"{self.node_id}" if scoped else "all sessions", style="bold")
        scope.append(f" · {len(self.shown)}")
        running = sum(t.running for t in self.terminals.values())
        if running:
            scope.append(f" · ▶ {running} running", style="green")
        self.query_one("#chat-scope", Static).update(scope)

        lst = self.query_one("#chat-sessions", OptionList)
        highlighted = lst.highlighted
        lst.clear_options()
        for s in self.shown:
            t = self.terminals.get(s.key)
            lst.add_option(Option(session_label(s, bool(t and t.running)), id=s.key))
        if not self.shown:
            hint = f"no sessions for {self.node_id} yet — n / a start one" if scoped else "no sessions found"
            lst.add_option(Option(Text(hint, style="dim"), disabled=True))
        elif highlighted is not None:
            lst.highlighted = min(highlighted, len(self.shown) - 1)

    def action_toggle_scope(self) -> None:
        self.all_scope = not self.all_scope
        self._render_list()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        session = next((s for s in self.shown if s.key == event.option_id), None)
        if session is not None:
            self.open_session(session)
        event.stop()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()  # session keys are not graph nodes; keep them away from the preview

    # -- terminals ---------------------------------------------------------------------------

    def _env(self) -> dict[str, str]:
        # The session hook links the session to this node (scripts/session_hook.py).
        return {"ORKCRAFT_TICKET": self.node_id} if self.node_id else {}

    def _show(self, key: str, command: list[str], harness: str = HARNESS_CLAUDE, title: str = "", env: dict[str, str] | None = None) -> Terminal:
        term = self.terminals.get(key)
        switcher = self.query_one("#chat-main", ContentSwitcher)
        if term is None or not term.running:
            if term is not None:
                term.remove()
            self._term_seq += 1
            merged_env = {**self._env(), **(env or {})}
            # 🪙 / 🪵 telemetry: the hook tags the session with this run and terminal.
            run_id = getattr(self.app, "run_id", "")
            if run_id:
                merged_env["ORKCRAFT_RUN"] = run_id
                merged_env["ORKCRAFT_TERMINAL"] = key
            # An orkspace with a worktree runs its sessions in that checkout (stage 12).
            session_cwd = getattr(self.app, "session_cwd", None)
            cwd = session_cwd() if callable(session_cwd) else self.app.repo_root  # type: ignore[attr-defined]
            term = Terminal(command, cwd=str(cwd), env=merged_env,  # type: ignore[attr-defined]
                            id=f"term-{self._term_seq}")
            term.key, term.harness, term.title = key, harness, title      # the core's session (core/sessions.py)
            self.terminals[key] = term
            self.meta[key] = (harness, title, self.node_id)
            switcher.mount(term)
        switcher.current = term.id
        self.call_after_refresh(term.focus)
        self._render_list()
        return term

    def open_session(self, session: Session) -> None:
        cmd = resume_command(session)
        if cmd is None:
            # Cloud session: nothing to attach to locally; show the link instead.
            self.app.notify(f"Cloud session — open {session.url}", title="Chat", timeout=8)
            return
        self._show(session.key, cmd, session.harness, session.title)

    def action_new_session(self, harness: str) -> None:
        self._new_count += 1
        self._show(f"new:{harness}:{self._new_count}", new_command(harness), harness, f"new {harness} session")

    def deploy(self, key_prefix: str, command: list[str], harness: str, title: str, env: dict[str, str] | None = None) -> str:
        self._deploy_count += 1
        key = f"{key_prefix}:{self._deploy_count}"
        self._show(key, command, harness, title, env=env)
        return key

    def show_session(self, key: str) -> None:
        """A session the core already runs (a deployed ork), in a terminal of its own."""
        s = self.app.tent.get(key)  # type: ignore[attr-defined]
        if s is not None:
            self._show(key, s.command, s.harness, s.title)

    def open_for_node(self, node_id: str) -> None:
        """Preview / card `o`: the node's latest resumable session, else a new Claude session."""
        self.node_id = node_id
        self.all_scope = False
        self.refresh_view()
        latest = next((s for s in self.shown if s.resumable), None)
        if latest is not None:
            self.open_session(latest)
        else:
            self.action_new_session(HARNESS_CLAUDE)

    def action_stop_session(self) -> None:
        current = self.query_one("#chat-main", ContentSwitcher).current
        for term in self.terminals.values():
            if term.id == current:
                term.stop()

    def show_terminal(self, key: str) -> None:
        term = self.terminals.get(key)
        if term is not None:
            self.query_one("#chat-main", ContentSwitcher).current = term.id
            self.call_after_refresh(term.focus)

    def send(self, key: str, data: bytes) -> None:
        term = self.terminals.get(key)
        if term is not None:
            term.write(data)

    def interrupt_all(self) -> int:
        """Halt All: interrupt every running session; returns how many were halted."""
        return sum(t.interrupt() for t in self.terminals.values())

    def action_focus_list(self) -> None:
        self.query_one("#chat-sessions", OptionList).focus()

    def on_terminal_exited(self, event: Terminal.Exited) -> None:
        # A finished session may have written its id through the hook: pick it up.
        self.refresh_view()

    @property
    def current_terminal(self) -> Terminal | None:
        current = self.query_one("#chat-main", ContentSwitcher).current
        return next((t for t in self.terminals.values() if t.id == current), None)
