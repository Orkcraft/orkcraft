"""The onboarding's shared pieces: the outcomes of the town step, a step's frame and its buttons."""
from __future__ import annotations

from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList

from orkcraft.hooks import install as hooks_install
from orkcraft.screens.build_flow import MODAL_CSS


CUSTOM = "custom"
EMPTY = "empty"
# what the guard step says about agy: hooks/install.py, shared with the window's onboarding
AGY_UNGUARDED, AGY_GUARDED, AGY_TOO_OLD = hooks_install.AGY_UNGUARDED, hooks_install.AGY_GUARDED, hooks_install.AGY_TOO_OLD
agy_warder_line = hooks_install.agy_warder_line


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
