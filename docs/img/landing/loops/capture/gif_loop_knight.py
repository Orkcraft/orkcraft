import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import giflib
from giflib import run, emit, open_building

giflib.SIM["work"] = "fixed in fix/checkout: charge() retries on StripeInvalidRequest"
TIMELINE = [
    (0.3, emit("watch", "mail.received", "Sentry: 500 /api/checkout", "Sentry alert")),
    (0.9, emit("watch", "mail.received", "Refund request · Pro plan", "Refund request")),
    (1.4, emit("tally", "charts.threshold", "spend $3.10 ≥ $3.00 (critical)", "over the cap")),
    (4.0, open_building("launcher")),
]
for mode, texts in run(Path(sys.argv[1]), Path(sys.argv[2]), "knight-night-watch", TIMELINE, seconds=5.0, size=(170, 42)):
    print(f"--- {mode} last\n" + "\n".join(texts[-1].splitlines()[:14]))
