import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from looplib import run

EMITS = [
    ("watch", "mail.received", "Sentry: 500 /api/checkout", "Sentry alert"),
    ("totem", "totem.routed", "Sentry: 500 /api/checkout", "bug"),
    ("totem", "totem.routed", "Refund request · Pro plan", "help"),
    ("grunts", "pool.done", "Fix checkout 500 — Smith · fix/checkout", "fix/checkout"),
    ("smithy", "forge.merged", "fix/checkout merged into main", "merged"),
    ("replies", "mill.done", "Re: Refund request — refunded", "reply"),
    ("tally", "charts.threshold", "spend $3.10 ≥ $3.00 (critical)", "over the cap"),
]
run(Path(sys.argv[1]), Path(sys.argv[2]), "knight-night-watch", EMITS, size=(170, 42))
