"""🎯 The Catapult's browser mode: when a site has no API, the Catapult works its form instead.

    scout    a visible browser opens `page` with the camp's own profile (log in once — the login
             stays in `.orkcraft/catapult/<id>/profile`, outside the camp's git); you get to the
             form, the Catapult marks every field and button it sees and remembers the clicks that
             led to the form since the last page load (`Events → Create event`); you close the
             window → the map is saved (`map.json`)
    plan     the cart's keys meet the map's fields: `fields` in the settings first
             ("Event name = title"), then the model's mapping (`m`, `mapping.json`), then plain
             name matching
    script   the plan becomes `fill.py` — a standalone Playwright script that reads the cart from
             stdin, opens the form (when its address alone does not show it, it opens the start
             page and repeats the clicks), fills it and then either hands it to you (`finish: leave`, you
             press the button) or presses `submit` itself (`finish: press`). A script edited by
             hand is kept (`fill.sha` knows what the Catapult wrote)
    fire     `python fill.py` with the cart on stdin; its last stdout line is the summary

Playwright is optional: `pip install 'orkcraft[browser]'` (and `playwright install chromium`).

The parts: scouting.py (the map), planning.py (the plan), fill_script.py (the script and its run),
repairs.py (the overseer's repair), forms.py (the intent's forms, the scout agent, files to upload).
"""
from __future__ import annotations

from orkcraft.realm.catapult_web.scouting import (  # noqa: F401
    INSTALL_HINT, WATCH_LIMIT_S, WATCH_TICK_S, PRESS_TIMEOUT_S, LEAVE_TIMEOUT_S,
    HELPERS_JS, SCOUT_JS, CLICK_JS, BANNER_JS, available, url_ok, load_map, save_map, _signature,
    path_to_form, scout, path_text, ensure_profile,
)
from orkcraft.realm.catapult_web.planning import (  # noqa: F401
    Step, Plan, field_name, _norm, _words, leaves, schema_paths, pick, _find_field, parse_rules, plan,
    describe, MAPPER, map_with_model, load_mapping, save_mapping,
)
from orkcraft.realm.catapult_web.fill_script import (  # noqa: F401
    SCRIPT, _step_data, script_text, _sha, edited_by_hand, write_script, Result, run_script,
)
from orkcraft.realm.catapult_web.repairs import (  # noqa: F401
    MAX_REPAIRS, KINDS, REPAIRER, Repair, _same_site, _fields_text, repair_prompt, apply_repair, repair,
)
from orkcraft.realm.catapult_web.forms import (  # noqa: F401
    FORM_NAME, Form, parse_forms, form_dir, rules_for, SCOUT_STEPS, DANGER, SCOUTER, LoginNeeded, _host,
    login_page, _elements, agent_scout, _settle, DOWNLOAD_LIMIT, resolve_files,
)
