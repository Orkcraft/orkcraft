"""Seams for the model calls: tests (and the demo) put a fake runner here; None means the real CLI.

One place for every face of orkcraft — the TUI and, later, the GUI read them at call time."""

BUILD_RUNNER = None
ELDERS_RUNNER = None        # tests: the Elders' model call (realm/elders.py)
RECRUIT_RUNNER = None     # tests replace the Recruiter's and the steward's Claude call
ROAD_RUNNER = None        # … and for the road planner (realm/road_planner.py: Listen in words)
STEWARD_RUNNER = None
FASTPATH_RUNNER = None    # tests put a fake light model for the Council's Fast Path here
OPTIMIZE_RUNNER = None    # … and for the Building retro's proposals
WEEKLY_RUNNER = None      # … and for the Town retro
ROUND_RUNNER = None       # … and for the Night round's words and ideas (core/workers/fields_round.py)
WARCHIEF_RUNNER = None    # … and for the Warchief's answers in the Town Hall (core/workers/town_hall.py)
KEEPER_RUNNER = None      # … and for a building's keeper (core/keeper.py)
