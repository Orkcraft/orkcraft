import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from classes import *
from orkcraft.realm import barracks as bk

ROOT = Path(sys.argv[1])
TOKEN_OLD = """def exchange_code(req):
    grant = codes.get(req.code)
    if grant is None:
        raise InvalidGrant()
    refresh = mint_refresh(grant.user)
    return TokenPair(access, refresh)
"""
TOKEN_NEW = """def exchange_code(req):
    grant = codes.pop(req.code, None)
    if grant is None:
        raise InvalidGrant()
    verify_pkce(req.verifier, grant)
    refresh = mint_refresh(grant.user, family=new_family())
    return TokenPair(access, refresh)
"""
TASKS = """# Sprint

## To Do
- [ ] T2103 Rotate signing keys
- [ ] T2104 Token TTL config

## In Progress
- [ ] Review auth refresh PR
- [ ] T2101 PKCE exchange

## Done
- [x] T2100 OAuth client
- [x] T2099 Login form
"""
sc = scenario("peon", "Feat-OAuth", "⛺", [
    typed("p_tasks", "fields", "Task Fields", "🌾", "Farmer", "the sprint's queue", "tent", path="TASKS.md"),
    typed("p_barracks", "barracks", "Barracks", "🏕️", "Grunts", "orcs in worktrees", "tent", max_orcs=3,
          providers=["claude", "agy"], budget_usd=5.0),
    typed("p_forge", "forge", "The Forge", "⚒️", "Smith", "branches, PRs, merge", "castle", test_cmd="pytest -q"),
    typed("p_lake", "lake", "Lake of Insight", "🌊", "Seer", "the diff, side by side", "dome"),
    typed("p_council", "council", "Orc Council", "🔥", "Chieftains", "reviews the patch", "pagoda",
          goal="Review the patch for feat/oauth", members=["Smith:claude", "Diff Inspector:claude", "Test Runner:agy"],
          max_rounds=4, budget_usd=2.0),
    typed("p_watch", "watchtower", "Watchtower", "🗼", "Lookout", "GitHub events", "flag", github="acme-orcs/oauth-camp"),
    typed("p_loot", "loot", "Loot Vault", "📦", "Quartermaster", "release files to accept", "snow"),
    typed("p_crag", "crag", "Tally Crag", "🪨", "Crag Carver", "tokens per building", "castle", source="tokens",
          orientation="horizontal", window="24h", warn=100000, crit=150000),
], {"TASKS.md": TASKS, "auth/token.py": TOKEN_OLD})
root = build(ROOT, sc)

branch(root, "feat/oauth", {"auth/token.py": TOKEN_NEW}, "PKCE code exchange", 3)
branch(root, "fix/ttl", {"auth/ttl.py": "TTL = 900\n"}, "token TTL from config", 5)
branch(root, "chore/deps", {"requirements.txt": "httpx==0.28\n"}, "bump httpx", 9)
fake_gh(root / ".orkcraft" / "bin", [
    {"number": 41, "state": "OPEN", "headRefName": "feat/oauth", "url": "",
     "title": "Review auth refresh PR", "isDraft": False},
    {"number": 42, "state": "OPEN", "headRefName": "fix/ttl", "url": "",
     "title": "Token TTL from config", "isDraft": False},
    {"number": 39, "state": "MERGED", "headRefName": "chore/deps", "url": "",
     "title": "Bump httpx", "isDraft": False}])

barracks(root, "p_barracks",
         [bk.PoolOrc("Smith", "claude", keys=["T2100"], done=3), bk.PoolOrc("Tinker", "agy", done=1, failed=1),
          bk.PoolOrc("Scout", "claude", done=2)],
         [],
         [bk.PoolTask("t3", "T2100 OAuth client", "x", "T2100", status="done", orc="Smith", result="client + tests"),
          bk.PoolTask("t4", "T2098 Session cookie", "x", "T2098", status="failed", orc="Tinker", error="tests failed")],
         [])

council(root, "p_council", "Review the patch for feat/oauth", [
    (1, "Smith", "draft", "patch v1"),
    (1, "Diff Inspector", "review", "OBJECT: new_family() is not persisted", False),
    (1, "Test Runner", "review", "OBJECT: 1 failing: test_refresh_reuse", False),
    (1, "Moderator", "revise", "sent back → v2"),
    (2, "Diff Inspector", "review", "AGREE", True),
    (2, "Test Runner", "review", "OBJECT: expired code accepted", False),
    (2, "Moderator", "revise", "sent back → v3"),
    (3, "Diff Inspector", "review", "AGREE", True)], 3, 0.62, draft="patch v3")

signals(root, "p_watch", [
    {"at": (NOW - dt.timedelta(minutes=m)).isoformat(), "source": s, "title": t, "body": b}
    for m, s, t, b in ((95, "cron", "09:00 triage", ""), (52, "github", "PR #42 opened", ""),
                       (31, "github", "Review asked: #41", ""),
                       (12, "github", "Check 'unit' failed", "feat/oauth · test_refresh_reuse\n1 failed, 48 passed"))])

ledger(root, [("forge", 0.9, 61000), ("forge", 1.1, 74000), ("lake", 0.4, 28000), ("council", 0.3, 22000),
              ("forge", 0.6, 39000), ("lake", 0.5, 31000), ("council", 0.2, 14000), ("barracks", 0.5, 33000),
              ("lake", 0.3, 18000), ("loot", 0.1, 9000), ("watchtower", 0.05, 3000)])

# what the agents wrote for the release, waiting in the working tree
write(root, "CHANGELOG.md", "# Changelog\n\n## v0.9.0\n- PKCE code exchange\n- refresh token rotation\n")
write(root, "docs/release.md", "# v0.9.0\n\nOAuth with PKCE.\n")

print(root)
