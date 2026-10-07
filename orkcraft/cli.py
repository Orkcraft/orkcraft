"""Command-line interface for orkcraft: the window (the default), the headless subcommands and the
deprecated TUI (`orkcraft tui`; docs/design/calm-town.md §9)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orkcraft.app import OrkcraftApp
from orkcraft.config import find_project_root


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


def _agy_global_yes(flag: bool | None) -> bool:
    """`--agy-global` / `--no-agy-global`, else ask the operator (no on a closed or piped stdin)."""
    if flag is not None:
        return flag
    from orkcraft.hooks import install as hooks_install
    if not sys.stdin.isatty():
        return False
    try:
        return input(hooks_install.AGY_GLOBAL_ASK + " [y/N] ").strip().lower() in ("y", "yes")
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
    hooks_p = subparsers.add_parser("hooks", help="Claude Code, Codex and agy hooks: session log and the Warder guard")
    hooks_p.add_argument("action", choices=("install", "uninstall"))
    agy_global = hooks_p.add_mutually_exclusive_group()
    agy_global.add_argument("--agy-global", dest="agy_global", action="store_true", default=None,
                            help="Also guard agy's headless steps in ~/.gemini/config/hooks.json, without asking")
    agy_global.add_argument("--no-agy-global", dest="agy_global", action="store_false",
                            help="Leave ~/.gemini/config/hooks.json alone, without asking")
    usage_p = subparsers.add_parser("usage", help="Anonymous usage stats: share them, stop, or see what is set")
    usage_p.add_argument("action", choices=("on", "off", "status"))
    fb_p = subparsers.add_parser("feedback", help="What the operator's quiet feedback weighs: calibrate the weights")
    fb_p.add_argument("action", choices=("calibrate",))
    fb_p.add_argument("--days", type=int, default=None, help="Only the last N days (default: all kept)")

    args = parser.parse_args(_demo_before_subcommand(sys.argv[1:] if argv is None else list(argv), subparsers.choices))

    if args.subcommand == "hooks":
        from orkcraft.hooks import install as hooks_install
        try:
            root = find_project_root(args.repo)
        except FileNotFoundError as e:
            sys.stderr.write(f"orkcraft error: {e}\n")
            return 1
        try:
            if args.action == "install":
                paths = hooks_install.install_all(root)
                if any(p.parent.name == ".agents" for p in paths) and _agy_global_yes(args.agy_global):
                    paths.append(hooks_install.install_agy_global())
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
            sys.stderr.write(f"orkcraft error: {e}\n")
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
        sys.stderr.write(f"orkcraft error: {e}\n")
        return 1

    auto_commit = not args.no_commit
    if args.subcommand == "gui":
        launch = _gui()
        if launch is None:
            return 1
        return launch.run(repo_root, auto_commit, args.layout, browser=args.browser, port=args.port)

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
