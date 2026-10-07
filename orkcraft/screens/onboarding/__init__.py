"""🧭 Onboarding: who you are → your day → the town → (the interview) → tools → autonomy and the quiet hours.

    Onboarding(app, machine_steps=True, town_step=True, on_town=app.raise_town).start()

The person comes first (design: docs/design/onboarding.md): the role and the industry, then a
typical day and its rhythm — both kept in the machine settings (`settings.profile`). Then the town:
the role's intents, those that fit the day first. When none fits, the interview asks about sources,
outputs, problems and AI tried, and the Town Builder adapts the role's templates to the answers.
The machine's part follows (tools and billing, the orks' autonomy and the quiet hours).

Nothing is written before the last step; Skip anywhere = an empty town, defaults for the rest,
no Warder. The town is raised over the map itself, with a progress bar along the bottom.

One module per part: `common` (a step's frame and buttons), `person` (experience, who you are,
questions with options), `town` (the role's intents), `machine` (AI tools and the day),
`raising` (the progress bar) and `flow` (`Onboarding`, which pushes the steps).
"""
from __future__ import annotations

import time

from orkcraft.screens.onboarding.common import (CUSTOM, EMPTY, _buttons, _css, _highlight,  # noqa: F401
                                                _highlighted_id, _nav, _title, hide_skip)
from orkcraft.screens.onboarding.person import Chip, PersonStep, QuestionsStep, XpStep  # noqa: F401
from orkcraft.screens.onboarding.town import IntentStep, intent_blurb, intent_label  # noqa: F401
from orkcraft.screens.onboarding.machine import (DETECTED, USE_OPTIONS, DayStep, ToolsStep,  # noqa: F401
                                                 day_legend, detect_all)
from orkcraft.screens.onboarding.raising import RaiseBar, mount_raise_bar, raising_steps  # noqa: F401
from orkcraft.screens.onboarding.flow import (INTERVIEW_STEPS, INTENT, PERSON, RULES, TOOLS, WHO_KEYS,  # noqa: F401
                                              XP, Onboarding)

STEP_PAUSE_S = 0.35        # each raising step stays on the bar long enough to be read


def pause() -> None:
    # Kept here, not in `raising`: STEP_PAUSE_S is read (and patched by tests) on this package.
    if STEP_PAUSE_S > 0:
        time.sleep(STEP_PAUSE_S)
