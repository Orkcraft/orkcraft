"""Command-line interface for orkcraft: the window (the default), the headless subcommands and the
deprecated TUI (`orkcraft tui`; docs/design/calm-town.md §9)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orkcraft.app import OrkcraftApp
from orkcraft.config import NOT_A_PROJECT_HINT, default_town_root, find_project_root


TUI_DEPRECATED = ("orkcraft: the terminal UI is deprecated and gets no new features; "
                  "the town lives in the window now: orkcraft gui (pip install 'orkcraft[gui]')\n")


def _gui(quiet: bool = False):
    """The GUI's launcher, or None (said why, unless `quiet`) when its packages are missing."""
    try:
        from orkcraft.gui import launch
    except ImportError as e:
        if not quiet:
            sys.stderr.write(f"orkcraft error: the GUI needs pip install 'orkcraft[gui]' ({e.name} is missing)\n")
        return None
    return launch


def _agy_global_yes(flag: bool | None, ask: str | None = None) -> bool:
    """`--agy-global` / `--no-agy-global`, else ask the operator (no on a closed or piped stdin)."""
    if flag is not None:
        return flag
    from orkcraft.hooks import install as hooks_install
    if not sys.stdin.isatty():
        return False
    try:
        return input((ask or hooks_install.AGY_GLOBAL_ASK) + " [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def _demo_before_subcommand(argv: list[str], subcommands) -> list[str]:
    """`orkcraft --demo gui`: the optional DIR of --demo would swallow the subcommand, so a
    subcommand right after it means the default sandbox (`--demo=`)."""
    out = list(argv)
    for i, word in enumerate(out[:-1]):
        if word == "--demo" and out[i + 1] in subcommands:
            out[i] = "--demo="
    return out


def _usage(action: str) -> int:
    """`orkcraft usage on|off|status` (core/usage.py, docs/usage-stats.md)."""
    from orkcraft import settings
    from orkcraft.core import usage
    machine = settings.load()
    if action != "status":
        usage.share(machine, action == "on")
        settings.save(machine)
    said = {True: "on", False: "off", None: "not asked yet (off)"}[machine.usage]
    print(f"usage stats: {said}")
    if machine.usage and machine.install_id:
        print(f"install id: {machine.install_id}")
    if usage.blocked():
        print(f"nothing is collected here: {usage.blocked()}")
    elif not usage.endpoint():
        print("nothing is sent: this build has no usage proxy")
    print("what is collected: docs/usage-stats.md")
    return 0


def _update(action: str | None) -> int:
    """`orkcraft update [check|auto|critical|ask]` (core/updates.py, docs/updates.md)."""
    from orkcraft import __version__, settings
    from orkcraft.core import updates
    machine = settings.load()
    if action in updates.POLICIES:
        machine.updates = action
        settings.save(machine)
    if action not in (None, "check"):
        print(f"updates: {machine.updates} — " + {
            "auto": "every update installs when the town opens",
            "critical": "critical updates install when the town opens; the others wait for `orkcraft update`",
            "ask": "nothing installs by itself; `orkcraft update` installs"}[machine.updates])
        return 0
    if updates.blocked():
        print(f"updates are off here: {updates.blocked()}")
        return 0
    try:
        found = updates.offer(updates.check(force=True, timeout=15.0).manifest)
    except Exception as e:
        sys.stderr.write(f"orkcraft error: the list of updates cannot be read ({e})\n")
        return 1
    way = updates.method()
    if found is None:
        print(f"orkcraft {__version__} is the latest")
        return 0
    print(f"orkcraft {found.version} is out{' — a critical update' if found.critical else ''} "
          f"(you have {__version__})")
    for line in found.notes:
        print(f"  {line}")
    if action == "check":
        print(f"install it: orkcraft update ({way.describe()})" if way.can else way.why)
        return 0
    if not way.can:
        sys.stderr.write(f"orkcraft error: {way.why}\n")
        return 1
    print(f"installing ({way.describe()})…")
    result = updates.install(way)
    updates.remember(result, found.version)
    if not result.ok:
        sys.stderr.write(f"orkcraft error: the update did not install:\n{result.output}\n")
        return 1
    print(f"installed orkcraft {result.version or found.version}; open the town again to run it")
    return 0


def _launching(args) -> bool:
    """The town opens (the window, the TUI, the showcase), as against a command that only says or sets."""
    return args.subcommand in (None, "gui", "tui") and args.demo_screens is None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orkcraft",
        description="Many coding agents in one project, as a real-time strategy game",
    )
    parser.add_argument("--repo", type=Path, default=None, help="Path to project root")
    parser.add_argument("--no-commit", action="store_true", help="Disable §10 per-action git commits")
    parser.add_argument("--layout", type=Path, default=None,
                        help="Window layout file (default: $ORKCRAFT_LAYOUT_FILE or ~/.config/orkcraft/layout.json)")
    parser.add_argument("--reset-layout", action="store_true", help="Start with the default window layout")
    parser.add_argument("--role", default=None, metavar="ROLE",
                        help="Who you are, as orkcraft.dev asked: a role (engineer, founder…) or a class "
                             "(peon, knight, elf, lich, gnome, goblin); the onboarding opens on it"),
    parser.add_argument("--demo", nargs="?", const="", default=None, metavar="DIR",
                        help="Open the showcase sandbox: simulated data (default ~/.orkcraft-demo)")
    parser.add_argument("--demo-reset", action="store_true", help="Rebuild the showcase sandbox")
    parser.add_argument("--demo-set", choices=("main", "managers", "dashboard"), default=None,
                        help="Which showcase: main (8 roles, F1–F8; the TUI's default), managers (1on1 prep) or "
                             "dashboard (every building type with its state; the GUI's default)")
    parser.add_argument("--demo-screens", type=Path, default=None, metavar="OUT",
                        help="With --demo: walk F1–F8 headless and save screenshots to OUT")

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # orkcraft tui
    subparsers.add_parser("tui", help="The terminal UI (deprecated: no new features)")
    gui_p = subparsers.add_parser("gui", help="Open the town in a window (the default; pip install 'orkcraft[gui]')")
    gui_p.add_argument("--browser", action="store_true", help="Open it in the browser instead of a window")
    gui_p.add_argument("--port", type=int, default=0, help="Port on 127.0.0.1 (default: any free one)")
    gui_p.add_argument("--demo", nargs="?", const="", default=argparse.SUPPRESS, metavar="DIR",
                       help="Open the showcase sandbox in the window")
    hooks_p = subparsers.add_parser("hooks", help="Every AI tool's hooks: session log and the Warder guard")
    hooks_p.add_argument("action", choices=("install", "uninstall"))
    agy_global = hooks_p.add_mutually_exclusive_group()
    agy_global.add_argument("--agy-global", dest="agy_global", action="store_true", default=None,
                            help="Also guard agy's headless steps in ~/.gemini/config/hooks.json, without asking")
    agy_global.add_argument("--no-agy-global", dest="agy_global", action="store_false",
                            help="Leave ~/.gemini/config/hooks.json alone, without asking")
    hermes_global = hooks_p.add_mutually_exclusive_group()
    hermes_global.add_argument("--hermes-global", dest="hermes_global", action="store_true", default=None,
                               help="Also guard Hermes in ~/.hermes/config.yaml, without asking")
    hermes_global.add_argument("--no-hermes-global", dest="hermes_global", action="store_false",
                               help="Leave ~/.hermes/config.yaml alone, without asking")
    usage_p = subparsers.add_parser("usage", help="Anonymous usage stats: share them, stop, or see what is set")
    usage_p.add_argument("action", choices=("on", "off", "status"))
    fb_p = subparsers.add_parser("feedback", help="What the operator's quiet feedback weighs: calibrate the weights")
    fb_p.add_argument("action", choices=("calibrate",))
    fb_p.add_argument("--days", type=int, default=None, help="Only the last N days (default: all kept)")
    up_p = subparsers.add_parser("update", help="Install the latest version, see what is out, or say what installs by itself")
    up_p.add_argument("action", nargs="?", choices=("check", "auto", "critical", "ask"), default=None,
                      help="check: only say what is out · auto | critical | ask: which updates install by "
                           "themselves when the town opens (default: critical)")

    words = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(_demo_before_subcommand(words, subparsers.choices))

    if args.subcommand == "update":
        return _update(args.action)

    if _launching(args) and args.demo is None:     # a critical fix lands before the town loads
        from orkcraft import settings as machine_settings
        from orkcraft.core import updates
        updates.at_launch(words, machine_settings.load().updates)

    if args.role is not None:
        from orkcraft import settings as machine_settings
        from orkcraft.realm import intents
        role_id = intents.role_id_of(args.role)
        if role_id is None:
            known = ", ".join([*intents.CLASSES, *(r.id for r in intents.ROLES)])
            sys.stderr.write(f"orkcraft error: no role {args.role!r}; one of: {known}\n")
            return 2
        machine_settings.preset_role(role_id, kin=intents.class_kin(args.role))   # gnome: the GUI asks which gnome

    if args.subcommand == "hooks":
        from orkcraft.hooks import install as hooks_install
        try:
            root = find_project_root(args.repo)
        except FileNotFoundError as e:
            sys.stderr.write(f"orkcraft error: {e}\n{NOT_A_PROJECT_HINT}\n")
            return 1
        try:
            if args.action == "install":
                paths = hooks_install.install_all(root)
                if any(p.parent.name == ".agents" for p in paths) and _agy_global_yes(args.agy_global):
                    paths.append(hooks_install.install_agy_global())
                if hooks_install.wants_hermes() and _agy_global_yes(args.hermes_global, hooks_install.HERMES_GLOBAL_ASK):
                    paths.append(hooks_install.install_hermes_global())
            else:
                paths = hooks_install.uninstall_all(root, agy_global=args.agy_global is not False)
        except ValueError as e:
            sys.stderr.write(f"orkcraft error: {e}\n")
            return 1
        for path in paths:
            print(f"{args.action}ed: {path}")
        if args.action == "install" and any(p.parent.name == ".codex" for p in paths):
            print(hooks_install.CODEX_TRUST)
        if args.action == "install" and any(p.parent.name == ".agents" for p in paths):
            print(hooks_install.AGY_TRUST)
        if not paths:
            print("nothing to uninstall")
        return 0

    if args.subcommand == "usage":
        return _usage(args.action)

    if args.subcommand == "feedback":
        from orkcraft.realm import calibrate
        try:
            root = find_project_root(args.repo)
        except FileNotFoundError as e:
            sys.stderr.write(f"orkcraft error: {e}\n{NOT_A_PROJECT_HINT}\n")
            return 1
        print(calibrate.render(calibrate.report(root, args.days)))
        return 0

    # No subcommand: the window when its packages are there, else the TUI (deprecated) as before.
    if args.subcommand is None and args.demo_screens is None and _gui(quiet=True) is not None:
        args.subcommand = "gui"
        for name, default in (("browser", False), ("port", 0)):
            setattr(args, name, getattr(args, name, default))

    if args.demo is not None:
        from orkcraft import demo
        if args.demo_set is None:          # the GUI draws the typed buildings; the TUI's showcase is the 8 roles
            args.demo_set = "dashboard" if args.subcommand == "gui" else "main"
        try:
            root = demo.build(Path(args.demo) if args.demo else demo.default_dir(args.demo_set),
                              reset=args.demo_reset, set_name=args.demo_set)
        except ValueError as e:
            sys.stderr.write(f"orkcraft error: {e}\n")
            return 1
        if args.demo_screens is not None:
            from orkcraft.demo.screens import take
            for path in take(root, args.demo_screens, args.demo_set):
                print(path)
            return 0
        if args.subcommand == "gui":
            launch = _gui()
            if launch is None:
                return 1
            return launch.run(root, False, root / ".orkcraft.json", demo=True, browser=args.browser, port=args.port)
        OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True).run()
        sys.stderr.write(TUI_DEPRECATED)
        return 0

    try:
        repo_root = find_project_root(args.repo)
    except FileNotFoundError as e:
        if args.repo is not None:          # a project was named: it has to be one
            sys.stderr.write(f"orkcraft error: {e}\n")
            return 1
        repo_root = default_town_root()    # opened outside any project (often ~ right after install)
        repo_root.mkdir(parents=True, exist_ok=True)
        sys.stderr.write(f"orkcraft: no project here, so the town is in {repo_root}. "
                         "To open a project's town: cd <project> && orkcraft, or orkcraft --repo <project>.\n")

    auto_commit = not args.no_commit
    if args.subcommand == "gui":
        launch = _gui()
        if launch is None:
            return 1
        from orkcraft.core import updates
        code = launch.run(repo_root, auto_commit, args.layout, browser=args.browser, port=args.port)
        if code == updates.RESTART:                # the window installed an update: it opens again on it
            updates.restart(words)
        return code

    # The TUI: asked for, or the window's packages are missing
    reset = args.reset_layout
    while True:                       # the weekly self-audit may ask for a fresh start
        app = OrkcraftApp(
            repo_root=repo_root,
            auto_commit=auto_commit,
            layout_file=args.layout,
            reset_layout=reset,
        )
        if app.run() != "restart":
            sys.stderr.write(TUI_DEPRECATED)
            return 0
        reset = False


if __name__ == "__main__":
    sys.exit(main())
