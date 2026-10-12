"""Count the model calls a town makes on its own (docs/design/script-first.md §2).

    python tools/count_model_calls.py [--carts N] [--ticks N] [--dislike BUILDING] [--fail BUILDING]

Builds the dashboard demo in a temporary folder and opens it as a real town (not the sandbox: there no
model is ever called), with every model seam replaced by a counter — `builders.ask` (every `-p` call:
the steward, the retros, the keeper, the Council's Fast Path) and `roads.run_agent` (an agent handler,
a Mill's `agent:` step). Then it drops N pastes into the Gates' Pit, ticks the host N times (the roads,
the workers' own refreshes, the retros with their schedules due) and prints who called a model, how
often, from which function, for which building. Nothing leaves the machine. The counting is
orkcraft/gui/idle_check.py, which `orkcraft check` runs on a quiet town.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--carts", type=int, default=20)
    ap.add_argument("--ticks", type=int, default=120)
    ap.add_argument("--dislike", default="")
    ap.add_argument("--fail", default="", help="a building whose worker reports ERROR from the start")
    ap.add_argument("--goal", action="append", default=[], help="BUILDING=thrift|balance|quality")
    ap.add_argument("--keep", default="", help="build the demo here instead of a temporary folder")
    args = ap.parse_args(argv)
    from orkcraft.gui import idle_check
    got = idle_check.count(args.ticks, args.carts, Path(args.keep) if args.keep else None, args.dislike, args.fail,
                           dict(pair.partition("=")[::2] for pair in args.goal), retros_every_minute=True)
    print(f"{args.carts} carts into the Pit, {args.ticks} ticks a minute apart: {got['calls']} model calls")
    for who, n in got["by"]:
        print(f"  {n:4d}  {who}")
    for bid, n in sorted(got["picked"].items(), key=lambda kv: -kv[1]):
        print(f"  Building retro picked {bid}: {n}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
