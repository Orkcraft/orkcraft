"""The onboarding's shared pieces: the outcomes of the town step, a step's frame and its buttons."""
from __future__ import annotations

from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList

from orkcraft import tools
from orkcraft.screens.build_flow import MODAL_CSS


CUSTOM = "custom"
EMPTY = "empty"
AGY_UNGUARDED = ("The 🛡 Warder does not guard agy yet: agy sessions run with only agy's own sandbox and "
                 "permission prompts, so start agy with --sandbox and keep secrets out of the project folder.")
AGY_GUARDED = ("The 🛡 Warder guards agy too, through .agents/hooks.json once agy trusts this folder. "
               "`orkcraft hooks install` asks before guarding agy's headless steps as well.")
AGY_TOO_OLD = ("The 🛡 Warder cannot guard {agy}: it needs agy {least} or later. agy sessions run with only agy's "
               "own sandbox and permission prompts, so start agy with --sandbox and keep secrets out of the "
               "project folder.")


def agy_warder_line(checked: bool, statuses: list[tools.ToolStatus] | None) -> str:
    """What the Warder step says about agy. Until its hook was checked on a live agy
    (`MachineSettings.agy_warder_checked`), that it does not guard agy yet; then whether this agy
    is recent enough for it."""
    if not checked or statuses is None:
        return AGY_UNGUARDED
    agy = next((st for st in statuses if st.id == "agy"), None)
    if agy is not None and agy.found and tools.agy_guardable(agy.version):
        return AGY_GUARDED
    least = ".".join(map(str, tools.AGY_WARDER_MIN))
    what = "agy, which is not installed here" if agy is None or not agy.found else \
        f"agy {agy.version}" if agy.version else "this agy, which does not say its version"
    return AGY_TOO_OLD.format(agy=what, least=least)


def _css(cls: str, width: int) -> str:
    return MODAL_CSS.format(cls=cls, border_color="$accent", title_color="$accent") + f"""
    {cls} > Vertical {{ width: {width}; }}
    {cls} .ob-buttons {{ height: auto; margin-top: 1; align-horizontal: right; }}
    {cls} .ob-buttons Button {{ margin-left: 1; }}
    {cls} .ob-note {{ color: $warning; height: auto; }}
    {cls} .ob-mascot {{ width: 16; height: auto; padding: 1 0 0 2; color: $accent; }}
    """


def _title(text: str, step: str) -> str:
    return f"{text}  ·  {step}" if step else text


def _buttons(*specs: tuple[str, str, str]) -> Horizontal:
    return Horizontal(*(Button(label, id=bid, variant=variant) for label, bid, variant in specs),  # type: ignore[arg-type]
                      classes="ob-buttons")


def _nav(can_back: bool, last: bool = False) -> Horizontal:
    return _buttons(*([("← Back", "ob-back", "default")] if can_back else []), ("Skip", "ob-skip", "default"),
                    ("Build", "ob-next", "success") if last else ("Next →", "ob-next", "primary"))


def hide_skip(screen: ModalScreen) -> None:
    """A newcomer is walked through every step: no Skip (Back still leads to the experience step)."""
    for b in screen.query("#ob-skip, #au-skip"):
        b.display = False


def _highlight(lst: OptionList, option_id: str) -> None:
    for i in range(lst.option_count):
        if lst.get_option_at_index(i).id == option_id:
            lst.highlighted = i
            return


def _highlighted_id(lst: OptionList) -> str:
    return "" if lst.highlighted is None else lst.get_option_at_index(lst.highlighted).id or ""
