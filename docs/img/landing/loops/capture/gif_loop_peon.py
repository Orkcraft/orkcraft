import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from giflib import run, emit, open_building

TIMELINE = [
    (0.3, emit("tasks", "tasks.status_changed", "T2101 PKCE flow", "T2101 → In Progress")),
    (0.6, emit("tally", "charts.threshold", "tokens 155k ≥ 150k (critical)", "over the cap")),
    (3.9, open_building("grunts")),
]
for mode, texts in run(Path(sys.argv[1]), Path(sys.argv[2]), "peon-red-green", TIMELINE, seconds=5.0):
    print(f"--- {mode} last\n" + "\n".join(texts[-1].splitlines()[:14]))
