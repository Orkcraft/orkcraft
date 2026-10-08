"""A building spec checked against its type: what a schema cannot check.

Part of orkcraft.realm.catalog, which re-exports every name here: import it from there."""
from __future__ import annotations

from orkcraft.realm.catalog import DEFAULT_TYPE, MAX_QUICK_ACTIONS, SIZE_ORDER, SIZES, TYPES, migrate


def validate(spec: dict) -> list[str]:
    """What a schema cannot check: the type exists, its events, actions, size and config."""
    errors: list[str] = []
    spec = migrate(spec)
    tid = spec.get("type") or DEFAULT_TYPE
    t = TYPES.get(tid)
    if t is None:
        return [f"type: unknown {tid!r}; choose one of {', '.join(TYPES)}"]
    if spec.get("size") is not None and spec["size"] not in SIZES:
        errors.append(f"size: {spec['size']!r} is not one of {', '.join(SIZE_ORDER)}")
    if spec.get("roof"):
        from orkcraft.realm import huts
        if spec["roof"] not in huts.ROOFS:
            errors.append(f"roof: no {spec['roof']!r}; choose one of {', '.join(huts.ROOFS)} or none")
    for ev in spec.get("events") or []:
        if t.event(ev) is None:
            errors.append(f"events: {tid} does not send {ev!r}; it sends {', '.join(e.id for e in t.events) or 'nothing typed'}")
    actions = spec.get("quick_actions") or []
    if len(actions) > MAX_QUICK_ACTIONS:
        errors.append(f"quick_actions: at most {MAX_QUICK_ACTIONS}")
    for a in actions:
        if t.action(a) is None:
            errors.append(f"quick_actions: {tid} has no action {a!r}; it has {', '.join(x.id for x in t.actions) or 'none'}")
    config = spec.get("config") or {}
    for key, value in config.items():
        rule = t.config.get(key)
        if rule is None:
            errors.append(f"config: {tid} takes no {key!r}; it takes {', '.join(t.config) or 'nothing'}")
            continue
        typ, allowed, _ = rule
        if typ is bool:
            ok_type = isinstance(value, bool)
        elif typ is float:
            ok_type = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            ok_type = isinstance(value, typ) and not isinstance(value, bool)
        if not ok_type:
            errors.append(f"config: {key} must be {typ.__name__}")
        elif isinstance(allowed, tuple) and typ in (int, float) and not allowed[0] <= value <= allowed[1]:
            errors.append(f"config: {key} must be between {allowed[0]} and {allowed[1]}")
        elif isinstance(allowed, tuple) and typ is str and value not in allowed:
            errors.append(f"config: {key} must be one of {', '.join(allowed)}")
        elif typ is str and len(value) > 300:
            errors.append(f"config: {key} is too long")
        elif typ is list and (len(value) > 10 or not all(isinstance(x, str) and len(x) <= 300 for x in value)):
            errors.append(f"config: {key} must be up to 10 strings")
    if tid == "scrolls" and isinstance(config.get("wiki"), str):
        w = config["wiki"].strip()
        if not w or w.startswith(("/", "~")) or ".." in w.replace("\\", "/").split("/"):
            errors.append("config: wiki must be a folder inside the project")
    if tid == "mill" and isinstance(config.get("steps"), list):
        from orkcraft.realm import mill
        errors += [f"config: steps: {e}" for e in mill.check(config["steps"])]
    if tid == "workshop" and isinstance(config.get("schedule"), str) and config["schedule"].strip():
        from orkcraft.realm import watch
        if not watch.schedule_ok(config["schedule"]):
            errors.append("config: schedule: say `every 15m`, `hourly`, `daily 05:00`, `weekly mon 09:00` or a 5-field cron")
    if tid == "watchtower":
        from orkcraft.realm import watch
        if isinstance(config.get("cron"), str) and not watch.schedule_ok(config["cron"]):
            errors.append("config: cron: say `every 15m`, `hourly`, `daily 05:00`, `weekly mon 09:00` or a 5-field cron")
        if isinstance(config.get("github"), str) and not watch.REPO.match(config["github"]):
            errors.append("config: github must be owner/repo")
        if isinstance(config.get("places"), list):
            from orkcraft.realm import places
            errors += [f"config: places: {x!r} is not a place: start it with {places.NAME_HINT}"
                       for x in config["places"] if places.place_of(x) is None]
        if isinstance(config.get("feeds"), list):
            from orkcraft.realm import feeds
            errors += [f"config: feeds: {e}" for e in feeds.check(config["feeds"])]
            if not config.get("webhook_port") and any("secret=" in str(x) for x in config["feeds"]):
                errors.append("config: feeds: secret= is for webhooks — set webhook_port too")
    if tid == "horn":
        from orkcraft.realm import horn
        if isinstance(config.get("sounds"), list):
            errors += [f"config: sounds: {e}" for e in horn.parse(config["sounds"])[1]]
        if isinstance(config.get("default"), str) and not horn.sound_ok(config["default"]):
            errors.append(f"config: default: choose {', '.join(horn.SOUNDS)} or an audio file")
        if isinstance(config.get("quiet"), str) and not horn.quiet_ok(config["quiet"]):
            errors.append("config: quiet: say `22:00-08:00`")
    if tid == "catapult":
        from orkcraft.realm import catapult_web
        if isinstance(config.get("forms"), list):
            errors += [f"config: forms: {e}" for e in catapult_web.parse_forms(config["forms"])[1]]
        if isinstance(config.get("fields"), list):
            errors += [f"config: fields: {e}" for e in catapult_web.parse_rules(config["fields"])[1]]
        if config.get("mode") == "browser" and not config.get("forms"):
            errors.append("config: mode: browser needs forms — `name = https://… | what to open`")
    if tid == "watchtower" and isinstance(config.get("wants"), dict):
        from orkcraft.realm import pipes
        if any(not isinstance(k, str) or not pipes.want_of(v) for k, v in config["wants"].items()):
            errors.append(f"config: wants: a source → one of {', '.join(pipes.WANTS)}")
    if tid == "barracks":
        from orkcraft.realm import paths, pipes
        kinds = ", ".join(paths.DEFAULT_WANTS)
        if isinstance(config.get("wants"), list) and any(pipes.want_of(w) not in paths.DEFAULT_WANTS for w in config["wants"]):
            errors.append(f"config: wants: choose among {kinds}")
        table = config.get("want_by_source")
        if isinstance(table, dict) and (len(table) > 20 or any(
                not isinstance(k, str) or not isinstance(v, str) or (v and pipes.want_of(v) not in paths.DEFAULT_WANTS)
                for k, v in table.items())):
            errors.append(f"config: want_by_source: a building id or type → one of {kinds} (at most 20)")
    if tid == "mine" and isinstance(config.get("repeats"), list):
        from orkcraft.realm import research, watch
        for line in config["repeats"]:
            rep = research.parse_repeat(line)
            if rep is None or not watch.schedule_ok(rep["every"]):
                errors.append(f"config: repeats: {str(line)[:60]!r} is not `<every> | <limit> | <question>`")
    if tid == "gramophone" and isinstance(config.get("key"), str):
        from orkcraft.realm import logins
        if not (logins.is_ref(config["key"]) or logins.ENV_NAME.match(config["key"])):
            errors.append("config: key names an environment variable (GEMINI_API_KEY) or a login (keychain:gemini), "
                          "never the key itself")
    if tid == "crag" and isinstance(config.get("charts"), list):
        from orkcraft.realm import metrics
        errors += [f"config: charts: {e}" for e in metrics.parse_charts(config["charts"])[1]]
    if tid == "signpost" and isinstance(config.get("rules"), list):
        from orkcraft.realm import signpost
        errors += [f"config: rules: {e}" for e in signpost.rules_of(config["rules"])[1]]
    if tid != DEFAULT_TYPE:
        for key, (_, _, required) in t.config.items():
            if required and key not in config:
                errors.append(f"config: {tid} needs {key!r}")
    return errors
