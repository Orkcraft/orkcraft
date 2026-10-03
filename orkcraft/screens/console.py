"""The lower RTS console: War Map (orkspaces), Clan Roster (contextual garrison), Command Card."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm.orcs import ALERT_ICON, BUILDER, COUNCIL, RESIDENT, WORKER, Orc

if TYPE_CHECKING:
    from orkcraft.app import FocusState
    from orkcraft.realm.roster import Roster
    from orkcraft.scroll import Orkspace, TownScroll


def orc_key(o: Orc) -> str:
    if o.category == RESIDENT:
        return f"orc:resident:{o.ref}"
    return f"orc:{o.category}:{o.building or o.ref or o.name}"


STATUS_DISPLAY = {
    "alert": f"{ALERT_ICON} Wait",
    "busy": "🔨 Busy",
    "idle": "💤 Idle",
    "frozen": "🛑 Frozen",
    "draft": "📝 Draft",
}

NEUTRAL_ACTIONS = [
    ("B", "[B] 🏗️ Build Window (Mason & Artisan)"),
    ("P", "[P] 📜 Window Presets Catalog"),
    ("S", "[S] 🧌 Summon Orc / Warband"),
    ("T", "[T] 🌲 Toggle Terrain (Dim / Black)"),
    ("G", "[G] ⎇ Worktree of this Orkspace"),
]

BUILDING_ACTIONS = [
    ("R", "[R] ➕ Recruit Orc"),
    ("L", "[L] 📜 Building Chronicles"),
    ("Y", "[Y] 🛤 Listen to Another Window (Road)"),
    ("U", "[U] 🚧 Remove the Incoming Road"),
    ("P", "[P] 📌 Pin / Unpin Window"),
    ("M", "[M] 🗖 Window Mode (Move / Resize)"),
    ("X", "[X] 💥 Demolish Window"),
    ("Z", "[Z] ↶ Revert to Previous Checkpoint"),
    ("K", "[K] 👍 Good Result (a Reference)"),
    ("F", "[F] 👎 Bad Result — What Went Wrong?"),
]

ROAD_ACTIONS = [
    ("H", "[H] 🔀 Handler of this Road"),
    ("U", "[U] 🚧 Remove this Road"),
]


def road_card(app, key: str) -> Text:
    """The road card of the console: source → target, event, filter, handler, carts."""
    from orkcraft import scroll as ts
    from orkcraft.realm import pipes
    from orkcraft.widgets.road_layer import split_key

    t = Text()
    target_id, road_id = split_key(key)
    scroll_obj = getattr(app, "scroll", None)
    found = ts.find_road(scroll_obj, road_id, target_id) if scroll_obj is not None else None
    if found is None:
        t.append("This road no longer exists.", style="dim")
        return t
    target, road = found
    src = scroll_obj.building(road.source)
    t.append(f"{src.icon + ' ' if src and src.icon else ''}{src.title if src else road.source}", style="bold")
    t.append("  →  ")
    t.append(f"{target.icon + ' ' if target.icon else ''}{target.title}\n", style="bold")
    signal = f"  ·  signal {road.label}" if road.label else ""
    t.append(f"Event: {pipes.label(road.event)}{signal}\n")
    flt = "; ".join(f"{k}={','.join(map(str, v)) if isinstance(v, list) else v}" for k, v in road.filter.items())
    t.append(f"Filter: {flt or 'none'}\n", style="" if flt else "dim")
    orc = target.garrison.handler(road.handler) if road.handler else None
    t.append(f"Handler: {orc.avatar} {orc.name} ({orc.kind})\n" if orc else "Handler: plain\n")
    counts: dict[str, int] = {}
    engine = getattr(app, "roads", None)
    for cart in getattr(engine, "carts", []):
        if cart.target == target_id and cart.road_id == road_id:
            counts[cart.status] = counts.get(cart.status, 0) + 1
    order = ("sent", "delivered", "filtered", "held", "error")
    carts = " · ".join(f"{counts[k]} {k}" for k in order if counts.get(k))
    t.append(f"Carts: {carts or 'none yet'}\n", style="" if carts else "dim")
    return t


def unit_details(app, orc: Orc) -> Text:
    """Kind, harness scheme, roads, re-run policy and the reason — and the steward's last report."""
    from orkcraft.realm import looks, tiers

    t = Text()
    t.append(f"{'Steward' if orc.lead else 'Handler'} · {looks.KIND_LABELS.get(orc.kind, orc.kind)}")
    if orc.tier_icon:
        t.append(f" · {tiers.label(orc.tier)}", style=tiers.TIER_STYLES.get(orc.tier or "", ""))
    scheme = looks.scheme_text(orc.harness, orc.kind)
    if scheme.plain:
        t.append("  ")
        t.append(scheme)
        t.append(f"  ({looks.scheme_long(orc.harness, orc.kind)})", style="dim")
    t.append("\n")
    for label in orc.roads:
        t.append(f"◂ {label}\n", style="dim")
    if not orc.lead and orc.run:
        restart = "restart on new data" if orc.run.get("restart_on_new") else "finish, then rerun"
        t.append(f"Rerun: {orc.run.get('quiet_s', 0)} s quiet · {restart}\n", style="dim")
    if orc.why:
        t.append(f"Why {orc.kind}: {orc.why}\n", style="italic dim")
    if orc.lead and orc.building:
        from orkcraft.realm import steward
        report = steward.load_report(getattr(app, "repo_root", None), orc.building) if getattr(app, "repo_root", None) else None
        if report:
            t.append(f"Last watch {report.get('ts', '')[:16].replace('T', ' ')}: "
                     f"{len(report.get('findings', []))} finding(s), {len(report.get('proposals', []))} proposal(s)\n")
        else:
            t.append("Not watched yet — [W] Watch now\n", style="dim")
    return t


def _spend_of(app, orc: Orc):
    from orkcraft.realm import roads, steward, unit_info

    repo = getattr(app, "repo_root", None)
    snap = getattr(app, "snapshot", None)
    if orc.category == RESIDENT and orc.building and repo is not None:
        if orc.lead:
            report = steward.load_report(repo, orc.building) or {}
            cost = report.get("cost_usd")
            spend = unit_info.Spend(usd=float(cost) if isinstance(cost, (int, float)) else None,
                                    runs=1 if report else 0)
        elif orc.kind in unit_info.FREE_KINDS:
            spend = unit_info.Spend(free=True)
        else:
            orc_id = orc.ref.split("/", 1)[1] if "/" in orc.ref else orc.ref
            spend = unit_info.handler_spend(roads.examples_file(repo, orc.building, orc_id))
    else:
        spend = unit_info.Spend()
    term = orc.session if orc.category == RESIDENT else (orc.ref if orc.category == WORKER else "")
    if term and snap is not None and term in snap.cost_by_terminal:
        spend = spend.add(unit_info.Spend(usd=snap.cost_by_terminal[term]))
    return spend


def _append_tier(t: Text, orc: Orc) -> None:
    """🔮 / ⚔ / ⛏ before a handler's name, in its tier's colour (stewards have none)."""
    from orkcraft.realm import tiers
    if orc.tier_icon:
        t.append(f"{orc.tier_icon} ", style=tiers.TIER_STYLES.get(orc.tier or "", ""))


def orc_info(app, orc: Orc) -> Text:
    from orkcraft.realm import unit_info

    t = Text()
    st = STATUS_DISPLAY.get(orc.status, f"{orc.status_icon} {orc.status.capitalize()}")
    name_style = "bold yellow" if orc.status == "alert" else "bold"
    t.append("★ " if orc.lead else "", style=name_style)
    _append_tier(t, orc)
    t.append(orc.name, style=name_style)
    t.append(f"  {st}\n", style="dim")
    b = app.building(orc.building) if orc.building else None
    for sentence in unit_info.orc_sentences(orc, f"{b.icon} {b.title}" if b else ""):
        t.append(sentence + "\n")
    snap = getattr(app, "snapshot", None)
    term = orc.session if orc.category == RESIDENT else (orc.ref if orc.category == WORKER else "")
    live = snap.model_by_terminal.get(term, "") if snap is not None and term else ""
    models = unit_info.models_of(orc, live)
    if models:
        t.append("Models: ", style="dim")
        for i, (letter, style, label) in enumerate(models):
            t.append(("  " if i else "") + letter, style=style)
            t.append(f" {label}", style="dim")
        t.append("\n")
    if orc.category == RESIDENT and not orc.lead and orc.kind not in unit_info.FREE_KINDS:
        if orc.session:
            meta = getattr(getattr(app, "chat", None), "meta", {}).get(orc.session)
            t.append(f"● deployed · {meta[1] if meta and meta[1] else orc.session}\n", style="green")
        else:
            t.append("not deployed — C opens a session\n", style="dim")
    spend = _spend_of(app, orc)
    t.append(spend.text())
    if term and snap is not None and snap.context_by_terminal.get(term):
        t.append(f" · {unit_info.fmt_tokens(snap.context_by_terminal[term])} in context", style="dim")
    return t


def orc_about(app, orc: Orc) -> str:
    """Why the orc is here: its role, its orders, what it does now."""
    from orkcraft.realm import unit_info

    b = app.building(orc.building) if orc.building else None
    return " ".join(unit_info.orc_sentences(orc, f"{b.icon} {b.title}" if b else ""))


def orc_runs(app, orc: Orc) -> Text:
    """One quiet line: what it spent over its runs, and its own 👍 / 👎."""
    from orkcraft.realm import feedback

    parts = [_spend_of(app, orc).text()]
    repo = getattr(app, "repo_root", None)
    if repo is not None and "/" in orc.ref:
        sc = feedback.scores(repo).get(orc.ref, {})
        parts.append(f"👍 {sc.get('likes', 0)} 👎 {sc.get('dislikes', 0)}")
    parts.append("● deployed" if orc.session else "not deployed")
    return Text(" · ".join(parts), style="dim", no_wrap=True, overflow="ellipsis")


def building_about(app, building_id: str) -> str:
    """Why the building is here: its own summary, else its type's, else its role."""
    from orkcraft.realm import catalog

    b = app.building(building_id)
    spec = app.spec_of(building_id) if hasattr(app, "spec_of") else None
    about = (spec or {}).get("summary") or ""
    if not about and spec:
        about = catalog.type_of(spec).summary
    return about or (b.role if b else "") or "No description yet."


def building_runs(app, building_id: str, roster: Roster) -> Text:
    """One quiet line: what the garrison spent, the week's runs, 👍 / 👎."""
    from orkcraft.realm import unit_info

    orcs = roster.garrison(building_id)
    total = unit_info.Spend(free=True)
    for o in orcs:
        total = total.add(_spend_of(app, o))
    parts = [total.text() if orcs else "🪙 nothing spent — no orcs"]
    repo = getattr(app, "repo_root", None)
    if repo is not None:                     # the steward's journal
        from orkcraft.realm import feedback
        j = feedback.journal(repo, building_id)
        parts.append(f"week: {j['runs']} runs ({j['ok']} ✓ {j['failed']} ✗) · {j['results']} results")
        parts.append(f"👍 {j['likes']} 👎 {j['dislikes']}")
    return Text(" · ".join(parts), style="dim", no_wrap=True, overflow="ellipsis")


def building_listens(app, building_id: str) -> Text:
    """Who the building listens to, and which orc (or a plain road) takes each cart."""
    from orkcraft import scroll as ts
    from orkcraft.realm import pipes, tiers

    t = Text(no_wrap=True, overflow="ellipsis")
    scroll_obj = getattr(app, "scroll", None)
    target = scroll_obj.building(building_id) if scroll_obj is not None else None
    roads = ts.incoming(scroll_obj, building_id) if scroll_obj is not None else []
    if not roads:
        t.append("Listens to nobody yet", style="dim")
        return t
    t.append("Listens: ", style="dim")
    for i, road in enumerate(roads):
        if i:
            t.append(" · ", style="dim")
        src = scroll_obj.building(road.source)
        t.append(f"◂ {src.icon + ' ' if src and src.icon else ''}{src.title if src else road.source}", style="bold")
        t.append(f" {road.label or pipes.label(road.event)}", style="dim")
        orc = target.garrison.handler(road.handler) if target and road.handler else None
        if orc is not None:
            icon = tiers.icon(tiers.orc_tier(orc.harness, orc.kind))
            t.append(f" → {orc.avatar} {icon + ' ' if icon else ''}{orc.name}")
        else:
            t.append(" → plain", style="dim")
    return t


QUICK_KEYS = ("[", "]")     # a selected building's two quick actions

RESIDENT_ACTIONS = [
    ("C", "[C] 💬 Deploy / Open Session"),
    ("T", "[T] ⚡ Orders & Trigger"),
    ("D", "[D] 🗑 Dismiss"),
    ("H", "[H] 🛑 Halt"),
    ("L", "[L] 📜 Unit Chronicles"),
]

UNIT_ACTIONS = [
    ("C", "[C] 💬 Unit Chat / Orders"),
    ("L", "[L] 📜 Unit Chronicles"),
    ("T", "[T] ⚡ Triggers"),
    ("H", "[H] 🛑 Halt Unit"),
]


def orkspace_has_alert(scroll_obj: TownScroll | None, ork: Orkspace, roster: Roster) -> bool:
    if scroll_obj is None:
        return bool(roster.alerts)
    is_active = (ork.id == scroll_obj.active_orkspace_id)
    for alert in roster.alerts:
        orc = next((o for o in roster.orcs if o.alert and o.alert.id == alert.id), None)
        if orc is not None and orc.building:
            b_ork = scroll_obj.orkspace_of(orc.building)
            if b_ork is not None and b_ork.id == ork.id:
                return True
        else:
            if is_active:
                return True
    return False


class WarMap(Vertical):
    """Left column: shows camp/orkspace list in Neutral, card in Building/Unit."""

    def compose(self) -> ComposeResult:
        yield Static("🗺️ WAR MAP (Orkspaces)", id="warmap-title", classes="console-title")
        yield OptionList(id="warmap-list")
        yield Static("[F1] 🏰 Main Camp", markup=False, id="warmap-content")
        yield Static("[F1-F8]   [N] New   [d] Del", markup=False, id="warmap-footer", classes="console-footer")

    def update_content(self, focus_state: FocusState, roster: Roster, biome: str) -> None:
        lst = self.query_one("#warmap-list", OptionList)
        content = self.query_one("#warmap-content", Static)
        scroll_obj = getattr(self.app, "scroll", None)

        lst.display = True
        content.display = False
        content.update(f"[F1] 🏰 Main Camp ({biome})")

        highlighted = lst.highlighted
        lst.clear_options()
        if scroll_obj is not None:
            active_idx = 0
            for i, ork in enumerate(scroll_obj.orkspaces):
                is_active = (ork.id == scroll_obj.active_orkspace_id)
                if is_active:
                    active_idx = i
                prefix = "▶ " if is_active else "  "
                hk = f"[{ork.hotkey}] " if ork.hotkey else ""
                mark = f" {ALERT_ICON}" if orkspace_has_alert(scroll_obj, ork, roster) else ""
                wt_mark = getattr(self.app, "worktree_marks", {}).get(ork.id, "")
                row_text = f"{prefix}{hk}{ork.icon} {ork.name} ({ork.biome}){' ' + wt_mark if wt_mark else ''}{mark}"
                lst.add_option(Option(Text(row_text, style="bold" if is_active else ""), id=f"orkspace:{ork.id}"))
            # The cursor follows the active orkspace unless the operator is browsing the list.
            if lst.has_focus and highlighted is not None and highlighted < lst.option_count:
                lst.highlighted = highlighted
            else:
                lst.highlighted = active_idx
        else:
            alerts_mark = f" {ALERT_ICON}" if roster.alerts else ""
            lst.add_option(Option(Text(f"▶ [F1] 🏰 Main Camp ({biome}){alerts_mark}", style="bold"), id="orkspace:main_camp"))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option_id or ""
        if oid.startswith("orkspace:"):
            target_id = oid.split(":", 1)[1]
            self.app.desktop.switch_orkspace(target_id)
        event.stop()

    def on_click(self, event: events.Click) -> None:
        if event.widget and event.widget.id == "warmap-footer":
            self.app.action_new_orkspace()
            event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key == "d" and self.query_one("#warmap-list", OptionList).display:
            self.action_delete_orkspace()
            event.stop()

    def action_delete_orkspace(self) -> None:
        """Remove the highlighted orkspace if it is empty and not the last one."""
        from orkcraft import scroll as ts

        lst = self.query_one("#warmap-list", OptionList)
        if lst.highlighted is None or lst.highlighted >= lst.option_count:
            return
        oid = lst.get_option_at_index(lst.highlighted).id or ""
        if not oid.startswith("orkspace:"):
            return
        app = self.app
        target_id = oid.split(":", 1)[1]
        was_active = app.scroll.active_orkspace_id == target_id
        try:
            ts.remove_orkspace(app.scroll, target_id)
        except ValueError as e:
            app.notify(str(e), title="War Map", severity="warning")
            return
        if was_active:
            # The canvas under the operator changed: same path as a switch (neutral, refresh).
            app.desktop.apply_orkspace(app.scroll.active_orkspace_id)
            app.desktop.post_message(app.desktop.OrkspaceChanged(app.scroll.active_orkspace_id))
        app.desktop.save()
        app.refresh_roster()


INVENTORY_W = 19     # the garrison's 22 columns less its border and the list's scrollbar


class ClanRoster(Vertical):
    """Centre column: accordion roster in Neutral, garrison in Building, card in Unit."""

    class BuildingSelected(Message):
        def __init__(self, building_id: str) -> None:
            super().__init__()
            self.building_id = building_id

    class OrcSelected(Message):
        def __init__(self, key: str) -> None:
            super().__init__()
            self.key = key

    def __init__(self, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self.folded_headers: set[str] = set()
        self.inventory_of: str | None = None      # the orc whose 🎒 inventory the list shows

    def compose(self) -> ComposeResult:
        yield Static("🧌 CLAN ROSTER", id="roster-title", classes="console-title")
        yield OptionList(id="roster-list")
        yield Static("", markup=False, id="roster-card")
        yield Static("[Space] Fold   [1-9] Select", markup=False, id="roster-footer", classes="console-footer")

    @staticmethod
    def _render_garrison_row(o: Orc, number: int, seen: set[str] | frozenset = frozenset()) -> Text:
        """Two lines for the narrow garrison: number, ❓ when it has a question you have not
        opened yet, tier, name and state; then its harness."""
        from orkcraft.realm import looks

        t = Text(no_wrap=True, overflow="ellipsis")
        name_style = "bold yellow" if o.status == "alert" else "bold"
        asks = o.alert.id not in seen if o.alert is not None else o.status == "alert"
        t.append(f"[{number}] ", style="dim")
        if asks:
            t.append("❓", style="bold black on yellow")
            t.append(" ")
        t.append("★ " if o.lead else "", style=name_style)
        _append_tier(t, o)
        t.append(o.name, style="bold yellow" if asks else name_style)
        if not asks:
            t.append(f" {o.status_icon}", style="dim")
        t.append("\n   ")
        if o.kind in ("chain", "script"):
            t.append(f"{looks.kind_icon(o.kind)} {o.kind} · no model", style="dim")
        elif o.harness:
            for i, step in enumerate(o.harness):
                if i:
                    t.append("→", style="dim")
                harness = str(step.get("harness", "?"))
                t.append(harness.split(":")[0], style=looks.HARNESS_STYLE.get(harness, "dim"))
        else:
            t.append(o.role or "—", style="dim")
        return t

    @staticmethod
    def _render_orc_row(o: Orc, number: int | None = None) -> Text:
        """Name and state only: what it does, its models and spend are in the Info panel."""
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append(f"[{number}] " if number is not None else "  • ")
        star = "★ " if o.lead else ""
        name_style = "bold yellow" if o.status == "alert" else "bold"
        t.append(star, style=name_style)
        _append_tier(t, o)
        t.append(o.name, style=name_style)
        st = STATUS_DISPLAY.get(o.status, f"{o.status_icon} {o.status.capitalize()}")
        st_style = "bold yellow" if o.status == "alert" else ("bold green" if o.status == "busy" else "dim")
        t.append(f"  {st}", style=st_style)
        return t

    def update_content(self, focus_state: FocusState, roster: Roster) -> None:
        title = self.query_one("#roster-title", Static)
        footer = self.query_one("#roster-footer", Static)
        lst = self.query_one("#roster-list", OptionList)
        card = self.query_one("#roster-card", Static)

        if focus_state.mode == "neutral":
            title.update("🧌 CLAN ROSTER")
            footer.update("[Space] Fold")
            card.display = False
            lst.display = True

            highlighted = lst.highlighted
            lst.clear_options()

            # Raised buildings
            raised = [w for w in self.app.desktop.windows if not w.hidden]
            for w in raised:
                b = self.app.building(w.window_id)
                if b is None:
                    continue
                garrison = roster.garrison(w.window_id)
                garrison_count = len(garrison)
                hid = f"header:building:{b.id}"
                is_folded = hid in self.folded_headers
                arrow = "▶" if is_folded else "▼"
                lst.add_option(Option(Text(f"{arrow} {b.icon} {b.title} ({garrison_count})", style="bold",
                                           no_wrap=True, overflow="ellipsis"), id=hid))
                if not is_folded:
                    for o in garrison:
                        lst.add_option(Option(self._render_orc_row(o), id=orc_key(o)))

            # Other categories
            groups = (
                (WORKER, "⚔️ Warband"),
                (COUNCIL, "🏛️ Council"),
                (BUILDER, "🔨 Builders"),
            )
            for cat, cat_title in groups:
                members = [o for o in roster.orcs if o.category == cat]
                hid = f"header:{cat}"
                is_folded = hid in self.folded_headers
                arrow = "▶" if is_folded else "▼"
                lst.add_option(Option(Text(f"{arrow} {cat_title} ({len(members)})", style="bold dim"), id=hid))
                if not is_folded:
                    for o in members:
                        lst.add_option(Option(self._render_orc_row(o), id=orc_key(o)))

            if highlighted is not None and highlighted < lst.option_count:
                lst.highlighted = highlighted

        elif focus_state.mode == "unit" and (orc := next(
                (o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None)) is not None \
                and orc.category in (RESIDENT, WORKER):
            self._show_inventory(orc)

        elif focus_state.mode in ("building", "road", "unit"):
            # The garrison stays: a selected orc is highlighted in it, its card is in the Info panel.
            orc = next((o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None) \
                if focus_state.mode == "unit" else None
            b_id = focus_state.building_id or (orc.building if orc else "") or ""
            if orc is not None and orc.category != RESIDENT:
                members = [o for o in roster.orcs if o.category == orc.category]
                label = {WORKER: "⚔️ Warband", COUNCIL: "🏛️ Council", BUILDER: "🔨 Builders"}.get(orc.category, "Orcs")
            else:
                members = roster.garrison(b_id)
                b = self.app.building(b_id)
                label = "🧌 GARRISON"
            title.update(label)
            footer.update("[1-9] · [Esc] Back" if focus_state.mode != "road" else "[H] · [U] · [Esc]")
            card.display = False
            lst.display = True
            prev = lst.highlighted
            lst.clear_options()
            for idx, o in enumerate(members, 1):
                lst.add_option(Option(self._render_garrison_row(o, idx, getattr(self.app, "seen_alerts", set())),
                                      id=orc_key(o)))
            if not members:
                lst.add_option(Option(Text("No orcs yet\nR recruits", style="dim"), disabled=True))
            keys = [orc_key(o) for o in members]
            if orc is not None and orc_key(orc) in keys:
                lst.highlighted = keys.index(orc_key(orc))
            elif prev is not None and prev < lst.option_count:
                lst.highlighted = prev          # the 1 s refresh must not undo the operator's cursor

    def _show_inventory(self, orc: Orc) -> None:
        """🎒 The selected orc's inventory: its model and tier (a button to change them), then
        the tools it reached for lately — each opens its history with that tool."""
        from orkcraft.realm import inventory, tiers

        self.query_one("#roster-title", Static).update("🎒 INVENTORY")
        self.query_one("#roster-footer", Static).update("[Enter] · [Esc] Back")
        self.query_one("#roster-card", Static).display = False
        lst = self.query_one("#roster-list", OptionList)
        lst.display = True
        prev = lst.highlighted if self.inventory_of == orc_key(orc) else None
        self.inventory_of = orc_key(orc)
        lst.clear_options()

        snap = getattr(self.app, "snapshot", None)
        term = orc.session if orc.category == RESIDENT else orc.ref
        live = snap.model_by_terminal.get(term, "") if snap is not None and term else ""
        models = inventory.models_of(orc, live)
        row = Text(no_wrap=True, overflow="ellipsis")
        if not models:
            row.append("🗿 no model", style="dim")
        for i, (tier, model) in enumerate(models[:2]):
            if i:
                row.append("→", style="dim")
            if tier:
                row.append(f"{tiers.icon(tier)} ", style=tiers.TIER_STYLES.get(tier, ""))
            row.append(model, style="bold")
        if len(models) > 2:
            row.append(f"·{len(models)}", style="dim")
        can_change = orc.category == RESIDENT and orc.kind not in ("chain", "script")
        if can_change:                     # the whole row is the button; ⇄ says so
            row.append(" ")
            row.append(" ⇄ ", style="bold black on #f2c66d")
        lst.add_option(Option(row, id="inv:model"))
        lst.add_option(Option(Text("── tools ──", style="dim"), disabled=True))
        repo = getattr(self.app, "repo_root", None)
        tools = inventory.recent_tools(repo, orc) if repo is not None else []
        for use in tools:
            t = Text(no_wrap=True, overflow="ellipsis")
            t.append("🔧 ")
            t.append(inventory.short_tool(use.name))
            count = Text(f" ×{use.count}", style="dim")
            t.truncate(INVENTORY_W - count.cell_len, overflow="ellipsis")
            lst.add_option(Option(Text.assemble(t, count), id=f"inv:tool:{use.name}"))
        if not tools:
            lst.add_option(Option(Text("no tool calls yet", style="dim"), disabled=True))
        if prev is not None and prev < lst.option_count:
            lst.highlighted = prev

    def toggle_fold(self, header_id: str) -> None:
        if header_id in self.folded_headers:
            self.folded_headers.remove(header_id)
        else:
            self.folded_headers.add(header_id)
        self.update_content(self.app.focus_state, self.app.roster)

    def on_key(self, event: events.Key) -> None:
        if event.key == "space":
            lst = self.query_one("#roster-list", OptionList)
            if lst.has_focus and lst.highlighted is not None:
                opt = lst.get_option_at_index(lst.highlighted)
                oid = opt.id or ""
                if oid.startswith("header:"):
                    self.toggle_fold(oid)
            if lst.has_focus:
                # Space belongs to the roster (fold): on an orc row it must not reach the War Horn.
                event.stop()
                event.prevent_default()
            return
        elif event.key in "123456789":
            lst = self.query_one("#roster-list", OptionList)
            if lst.has_focus and getattr(self.app, "focus_state", None) and self.app.focus_state.mode in ("building", "unit"):
                idx = int(event.key) - 1
                orc_ids = [o.id for o in (lst.get_option_at_index(i) for i in range(lst.option_count))
                           if o.id and o.id.startswith("orc:")]
                if idx < len(orc_ids):
                    self.post_message(self.OrcSelected(orc_ids[idx]))
                    event.stop()
                    return

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option_id or ""
        if oid.startswith("header:building:"):
            building_id = oid.split(":", 2)[2]
            self.post_message(self.BuildingSelected(building_id))
        elif oid.startswith("header:"):
            self.toggle_fold(oid)
        elif oid.startswith("orc:"):
            self.post_message(self.OrcSelected(oid))
        elif oid.startswith("inv:"):
            self._use_inventory(oid)
        event.stop()

    def _use_inventory(self, oid: str) -> None:
        orc = next((o for o in self.app.roster.orcs if orc_key(o) == self.inventory_of), None)
        if orc is None:
            return
        if oid == "inv:model":
            self.app.open_orc_model(orc)
        elif oid.startswith("inv:tool:"):
            from orkcraft.screens.chronicles_view import UnitChronicles
            self.app.push_screen(UnitChronicles(orc, self.app.repo_root, tool=oid.split(":", 2)[2]))


class UnitInfo(Vertical):
    """The Info panel: what the selected orc, building or road is, its models, its spend.
    A building: its name with 👍 / 👎 / 🗑, why it is here, a quiet line of its runs (📜 history)
    and who it listens to (➕ adds a road)."""

    def compose(self) -> ComposeResult:
        yield Static("ℹ INFO", id="info-title", classes="console-title")
        with Vertical(id="info-building"):
            with Horizontal(id="ib-head", classes="ib-row"):
                yield Static("", id="ib-name", markup=False)
                yield Static(" 👍 ", id="ib-like", classes="ib-button")
                yield Static(" 👎 ", id="ib-dislike", classes="ib-button")
                yield Static(" 🗑 ", id="ib-demolish", classes="ib-button")
            yield Static("", id="ib-about", markup=False)
            with Horizontal(id="ib-runs-row", classes="ib-row"):
                yield Static("", id="ib-runs", markup=False)
                yield Static(" 📜 History ", id="ib-history", classes="ib-button")
            with Horizontal(id="ib-listens-row", classes="ib-row"):
                yield Static("", id="ib-listens", markup=False)
                yield Static(" ➕ Listen ", id="ib-listen", classes="ib-button")
        with Vertical(id="info-orc"):
            with Horizontal(classes="ib-row"):
                yield Static("", id="io-name", markup=False)
                yield Static(" 👍 ", id="io-like", classes="ib-button")
                yield Static(" 👎 ", id="io-dislike", classes="ib-button")
                yield Static(" 🗑 ", id="io-dismiss", classes="ib-button")
            yield Static("", id="io-about", markup=False)
            with Horizontal(classes="ib-row"):
                yield Static("", id="io-runs", markup=False)
                yield Static(" 📜 History ", id="io-history", classes="ib-button")
        yield Static("", markup=False, id="info-body")

    def update_content(self, focus_state: FocusState, roster: Roster) -> None:
        title = self.query_one("#info-title", Static)
        body = self.query_one("#info-body", Static)
        building = self.query_one("#info-building", Vertical)
        orc_box = self.query_one("#info-orc", Vertical)
        self.building_id = None
        self.orc = None
        building.display = orc_box.display = False
        body.display = True
        if focus_state.mode == "unit":
            orc = next((o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None)
            title.update("ℹ INFO" if orc and orc.category == RESIDENT else f"ℹ {orc.name}" if orc else "ℹ INFO")
            if orc is not None and orc.category == RESIDENT:
                self.orc = orc
                orc_box.display, body.display = True, False
                head = Text(no_wrap=True, overflow="ellipsis")
                head.append(f"{orc.icon} ")
                _append_tier(head, orc)
                head.append(("★ " if orc.lead else "") + orc.name, style="bold")
                b = self.app.building(orc.building) if orc.building else None
                if b is not None:
                    head.append(f"  · {b.icon} {b.title}", style="dim")
                self.query_one("#io-name", Static).update(head)
                self.query_one("#io-about", Static).update(orc_about(self.app, orc))
                self.query_one("#io-runs", Static).update(orc_runs(self.app, orc))
                self.query_one("#io-dismiss").display = not orc.lead       # a steward stays
            else:
                body.update(orc_info(self.app, orc) if orc else Text("This orc is gone.", style="dim"))
        elif focus_state.mode == "building":
            bid = focus_state.building_id or ""
            b = self.app.building(bid)
            title.update("ℹ INFO")
            if b is None:
                body.update(Text("This building is gone.", style="dim"))
                return
            self.building_id = bid
            building.display, body.display = True, False
            self.query_one("#ib-name", Static).update(Text(f"{b.icon} {b.title}", style="bold"))
            self.query_one("#ib-about", Static).update(building_about(self.app, bid))
            self.query_one("#ib-runs", Static).update(building_runs(self.app, bid, roster))
            self.query_one("#ib-listens", Static).update(building_listens(self.app, bid))
        elif focus_state.mode == "road":
            title.update("ℹ 🛤 Road")
            body.update(road_card(self.app, focus_state.road_key or ""))
        else:
            title.update("ℹ INFO")
            body.update(Text("Select a building or an orc: what it does, its models and what it cost show here.",
                             style="dim"))

    def on_click(self, event: events.Click) -> None:
        wid = getattr(event.widget, "id", "") or ""
        orc = getattr(self, "orc", None)
        if orc is not None and wid.startswith("io-"):
            app = self.app
            if wid == "io-like":
                app.like_orc(orc)
            elif wid == "io-dislike":
                app.dislike_orc(orc)
            elif wid in ("io-dismiss", "io-history"):
                app.action_command_card("D" if wid == "io-dismiss" else "L")
            else:
                return
            event.stop()
            return
        bid = getattr(self, "building_id", None)
        if not bid or not wid.startswith("ib-"):
            return
        app = self.app
        if wid == "ib-like":
            app.like_building(bid)
        elif wid == "ib-dislike":
            app.dislike_building(bid)
        elif wid in ("ib-demolish", "ib-history", "ib-listen"):
            app.action_command_card({"ib-demolish": "X", "ib-history": "L", "ib-listen": "Y"}[wid])
        else:
            return
        event.stop()


class CommandCard(Vertical):
    """Right column: clickable actions for the current focus state."""

    def compose(self) -> ComposeResult:
        yield Static("⚒️ COMMAND CARD", id="command-title", classes="console-title")
        yield OptionList(id="command-actions")
        yield Static("[Esc] Deselect / Neutral Mode", markup=False, id="command-footer", classes="console-footer")

    def update_content(self, focus_state: FocusState, roster: Roster) -> None:
        actions_list = self.query_one("#command-actions", OptionList)
        highlighted = actions_list.highlighted
        actions_list.clear_options()

        if focus_state.mode == "neutral":
            actions = NEUTRAL_ACTIONS
        elif focus_state.mode == "building":
            # Only what this building can do: the common commands are keys (and Info's buttons).
            actions = []
            b_id = focus_state.building_id
            spec = getattr(self.app, "custom_specs", {}).get(b_id) if b_id else None
            if spec and "actions" in spec:
                for act in spec["actions"]:
                    actions.append((act["key"], f"[{act['key']}] {act['label']}"))
            spec = self.app.spec_of(b_id) if hasattr(self.app, "spec_of") else spec
            if spec:                                         # the hut's quick actions
                from orkcraft.realm import catalog
                quick = [(f"QA{key}", f"[{key}] {qa.glyph} {qa.label}")
                         for key, qa in zip(QUICK_KEYS, catalog.quick_actions_of(spec))]
                actions = quick + actions
        elif focus_state.mode == "unit":
            orc = next((o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None)
            if orc and orc.category == RESIDENT:
                actions = list(RESIDENT_ACTIONS)
                if orc.lead:
                    actions.append(("W", "[W] 🔎 Watch now (steward)"))
            else:
                actions = list(UNIT_ACTIONS)
            if orc and orc.alert:
                actions.insert(0, ("ENTER", "[Enter] ❓ Resolve Alert"))
        elif focus_state.mode == "road":
            actions = ROAD_ACTIONS
        else:
            actions = NEUTRAL_ACTIONS

        for key, label in actions:
            actions_list.add_option(Option(Text(label), id=f"action:{key}"))
        # A building with no commands of its own leaves the room to the Info panel; a garrison or
        # War Tent orc is commanded in its chat, which stands where the card was.
        chat = False
        if focus_state.mode == "unit":
            from orkcraft.screens.orc_chat import OrcChat
            chat = OrcChat.supports(next((o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None))
        self.set_class((not actions and focus_state.mode == "building") or chat, "-empty")

        if highlighted is not None and highlighted < actions_list.option_count:
            actions_list.highlighted = highlighted

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option_id or ""
        if oid.startswith("action:"):
            key = oid.split(":", 1)[1]
            if key.startswith("QA"):
                self.app.action_quick_action(QUICK_KEYS.index(key[2:]))
            elif key == "ENTER":
                orc = next((o for o in self.app.roster.orcs if orc_key(o) == self.app.focus_state.orc_key), None)
                if orc and orc.alert:
                    self.app.open_alert(orc.alert, orc.name)
            elif (
                getattr(self.app, "focus_state", None)
                and self.app.focus_state.mode == "building"
                and any(a.get("key") == key for a in getattr(self.app, "custom_specs", {}).get(self.app.focus_state.building_id, {}).get("actions", []))
            ):
                self.app.action_custom_action(key)
            else:
                self.app.action_command_card(key)
        event.stop()


CONSOLE_DEFAULT_PCT = 15   # of the screen height (33 → 22 → 15 %: the operator asked for more room for the town)
CONSOLE_MIN_PCT, CONSOLE_MAX_PCT = 10, 60


class Console(Horizontal):
    """RTS console at the bottom of the screen (33/33/33 columns). Its height is a share of the
    screen: drag the top edge or press alt+- / alt+=; the app keeps it in the Town Scroll."""

    class Resized(Message):
        """The operator changed the console height (end of a drag, or a key)."""
        def __init__(self, pct: int) -> None:
            super().__init__()
            self.pct = pct

    height_pct = CONSOLE_DEFAULT_PCT
    _drag_start: int | None = None

    def on_mount(self) -> None:
        self.border_title = "⇕"

    def set_height_pct(self, pct: int) -> int:
        pct = max(CONSOLE_MIN_PCT, min(CONSOLE_MAX_PCT, int(pct)))
        self.height_pct = pct
        if self.has_class("-floating"):
            layout = getattr(self.app, "layout_console", None)   # the town places it in cells
            if layout is not None:
                layout()
        else:
            self.styles.height = f"{pct}%"
        return pct

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1 and event.screen_y == self.region.y:   # the top edge is the grip
            self._drag_start = event.screen_y
            self.add_class("-dragging")
            self.capture_mouse()
            event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._drag_start is None:
            return
        # A % height is a share of the screen minus the HUD and the Footer (one row each); the
        # console spans from the pointer row down to its current bottom (the Footer's row).
        avail = max(self.app.size.height - 2, 1)
        rows = self.region.bottom - event.screen_y
        self.set_height_pct(round(rows * 100 / avail))
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._drag_start is None:
            return
        self._drag_start = None
        self.remove_class("-dragging")
        self.release_mouse()
        self.post_message(self.Resized(self.height_pct))
        event.stop()

    DEFAULT_CSS = """
    Console {
        height: 22%;
        min-height: 6;
        border-top: heavy $accent 45%;
        border-title-align: center;
        border-title-color: $accent 70%;
        background: $background;
    }
    Console.-dragging {
        border-top: heavy $warning;
    }
    /* Town view: a layer over the map's bottom edge, out of the layout, so the town keeps
       the whole height. Calm (nothing selected): the War Map alone. */
    Console.-floating {
        position: absolute;
        layer: overlay;
        min-height: 3;
    }
    Console.-floating.-calm #clan-roster, Console.-floating.-calm #unit-info, Console.-floating.-calm #command-card {
        display: none;
    }
    Console.-floating.-calm #warmap {
        width: 100%;
        max-width: 100%;
    }
    .console-col {
        height: 100%;
    }
    /* War Map (46) · Info (the rest) · garrison / inventory (22) · Command Card. */
    #warmap {
        width: 46;
    }
    #clan-roster {
        width: 22;
        border-left: vkey $accent 60%;
    }
    #unit-info {
        width: 1fr;
        border-left: vkey $accent 60%;
    }
    #info-body {
        height: 1fr;
        padding: 0 1;
    }
    #info-building {
        height: 1fr;
        padding: 0 1;
        display: none;
    }
    .ib-row { height: 1; }
    #ib-name, #ib-runs, #ib-listens { width: 1fr; }
    #ib-about, #io-about { height: auto; max-height: 3; color: $text; }
    #info-orc {
        height: 1fr;
        padding: 0 1;
        display: none;
    }
    #io-name, #io-runs { width: 1fr; }
    .ib-button { width: auto; margin-left: 1; background: $surface; text-style: bold; }
    .ib-button:hover { background: $warning; color: $background; }
    #ib-like, #io-like { background: $success 60%; }
    #ib-dislike, #io-dislike { background: $error 60%; }
    #command-card {
        width: 32;
        border-left: vkey $accent 60%;
    }
    #command-card.-empty { display: none; }
    .console-title {
        height: 1;
        text-style: bold;
        color: $accent;
        padding: 0 1;
        background: $surface;
    }
    .console-footer {
        dock: bottom;
        height: 1;
        color: $text-muted;
        padding: 0 1;
        background: $surface;
    }
    #warmap-list {
        height: 1fr;
        background: transparent;
        border: none;
        padding: 0;
    }
    #warmap-content {
        height: 1fr;
        padding: 1 1;
        display: none;
    }
    #roster-list {
        height: 1fr;
        background: transparent;
        border: none;
        padding: 0;
    }
    #roster-card {
        height: 1fr;
        padding: 0 1;
        display: none;
    }
    #command-actions {
        height: 1fr;
        background: transparent;
        border: none;
        padding: 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield WarMap(id="warmap", classes="console-col")
        yield UnitInfo(id="unit-info", classes="console-col")       # the wide Info sits beside the map
        yield ClanRoster(id="clan-roster", classes="console-col")
        yield CommandCard(id="command-card", classes="console-col")

    def refresh_state(self, focus_state: FocusState, roster: Roster) -> None:
        # The roster timer can fire while the app shuts down and the columns are already gone.
        if not self.is_attached or len(self.children) < 4:
            return
        biome = getattr(self.app.desktop, "biome", "forest")
        try:
            self.query_one(WarMap).update_content(focus_state, roster, biome)
            self.query_one(ClanRoster).update_content(focus_state, roster)
            self.query_one(UnitInfo).update_content(focus_state, roster)
            self.query_one(CommandCard).update_content(focus_state, roster)
        except NoMatches:
            # Shutdown unmounts the columns' children before the columns themselves.
            return

    def focus_roster(self) -> None:
        if self.has_class("-calm"):        # the calm town shows the War Map only
            self.query_one(WarMap).query_one("#warmap-list", OptionList).focus()
            return
        self.query_one(ClanRoster).query_one("#roster-list", OptionList).focus()
