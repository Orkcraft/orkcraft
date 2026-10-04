import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from looplib import run

EMITS = [
    ("tasks", "tasks.status_changed", "T2101 PKCE flow", "T2101 → In Progress"),
    ("grunts", "pool.done", "T2101 PKCE flow — Smith · feat/oauth", "T2101 done"),
    ("review", "team.artifact_ready", "patch agreed in round 3", "verdict"),
    ("smithy", "forge.conflict", "feat/oauth: test_refresh_reuse failed", "red tests"),
    ("smithy", "forge.merged", "fix/ttl merged into main", "merged"),
    ("tally", "charts.threshold", "tokens 155k ≥ 150k (critical)", "over the cap"),
]
run(Path(sys.argv[1]), Path(sys.argv[2]), "peon-red-green", EMITS)
