"""Command-line interface for orkcraft supporting headless subcommands and TUI launch."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orkcraft.app import OrkcraftApp
from orkcraft.config import find_project_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orkcraft",
        description="Terminal UI harness for multi-agent systems",
    )
    parser.add_argument("--repo", type=Path, default=None, help="Path to project root")
    parser.add_argument("--no-commit", action="store_true", help="Disable §10 per-action git commits")
    parser.add_argument("--layout", type=Path, default=None,
                        help="Window layout file (default: $ORKCRAFT_LAYOUT_FILE or ~/.config/orkcraft/layout.json)")
    parser.add_argument("--reset-layout", action="store_true", help="Start with the default window layout")
    parser.add_argument("--demo", nargs="?", const="", default=None, metavar="DIR",
                        help="Open the showcase sandbox: simulated data (default ~/.orkcraft-demo)")
    parser.add_argument("--demo-reset", action="store_true", help="Rebuild the showcase sandbox")
    parser.add_argument("--demo-set", choices=("main", "managers", "dashboard"), default="main",
                        help="Which showcase: main (8 roles, F1–F8), managers (1on1 prep) or dashboard (typed buildings)")
    parser.add_argument("--demo-screens", type=Path, default=None, metavar="OUT",
                        help="With --demo: walk F1–F8 headless and save screenshots to OUT")

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # orkcraft tui
    subparsers.add_parser("tui", help="Launch interactive Textual TUI (default)")
    hooks_p = subparsers.add_parser("hooks", help="Claude Code and Codex hooks: session log and the Warder guard")
    hooks_p.add_argument("action", choices=("install", "uninstall"))

    args = parser.parse_args(argv)

    if args.subcommand == "hooks":
        from orkcraft.hooks import install as hooks_install
        try:
            root = find_project_root(args.repo)
        except FileNotFoundError as e:
            sys.stderr.write(f"orkcraft error: {e}\n")
            return 1
        try:
            paths = (hooks_install.install_all if args.action == "install" else hooks_install.uninstall_all)(root)
        except ValueError as e:
            sys.stderr.write(f"orkcraft error: {e}\n")
            return 1
        for path in paths:
            print(f"{args.action}ed: {path}")
        if args.action == "install" and any(p.parent.name == ".codex" for p in paths):
            print(hooks_install.CODEX_TRUST)
        if not paths:
            print("nothing to uninstall")
        return 0

    if args.demo is not None:
        from orkcraft import demo
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
        OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True).run()
        return 0

    try:
        repo_root = find_project_root(args.repo)
    except FileNotFoundError as e:
        sys.stderr.write(f"orkcraft error: {e}\n")
        return 1

    # Default: launch TUI
    auto_commit = not args.no_commit
    reset = args.reset_layout
    while True:                       # the weekly self-audit may ask for a fresh start
        app = OrkcraftApp(
            repo_root=repo_root,
            auto_commit=auto_commit,
            layout_file=args.layout,
            reset_layout=reset,
        )
        if app.run() != "restart":
            return 0
        reset = False


if __name__ == "__main__":
    sys.exit(main())
