"""The eight showcase orkspaces of the landing page: one closed workflow per canvas.

Data only — `orkcraft.demo.build` turns it into a sandbox project. Everything here is
simulated: tasks, logs, diffs and reports look like a real project, none of it is.
Buildings are custom (Mason) buildings; their panes read the sandbox through the whitelisted
sources. Roads use the two real events; `label` is the signal's display name.
"""
from __future__ import annotations

SEL, TASK = "on_selection_change", "on_task_completed"
C, A = {"role": "run", "harness": "claude"}, {"role": "write", "harness": "agy", "tier": "warrior"}
REVIEW = {"role": "review", "harness": "claude", "tier": "warrior"}
# 🔮 elder · ⚔ warrior · ⛏ laborer (realm/tiers.py)
ELDER, WARRIOR, LABORER = ({**C, "tier": t} for t in ("elder", "warrior", "laborer"))


def pane(widget: str, data: str, title: str = "", ratio: int = 1, columns: list[str] | None = None) -> dict:
    p = {"widget": widget, "data": data, "ratio": ratio}
    if title:
        p["title"] = title
    if columns:
        p["columns"] = columns
    return p


def nodes(tag: str, limit: int = 20, **params) -> dict:
    return {"source": "graph_nodes", "params": {"tag": tag, "limit": limit, **params}}


def file(path: str) -> dict:
    return {"source": "file", "params": {"path": path}}


def tail(path: str, lines: int = 40) -> dict:
    return {"source": "file_tail", "params": {"path": path, "lines": lines}}


def building(bid, title, icon, orc, role, data: dict, panes, direction="", summary=""):
    # windows are wide and short: one pane + the 📥 pane side by side, two panes stacked
    direction = direction or ("horizontal" if len(panes) == 1 else "vertical")
    return {"id": bid, "title": title, "icon": icon, "summary": summary or role,
            "orc": {"name": orc, "role": role},
            "data": [{"name": k, **v} for k, v in data.items()],
            "layout": {"direction": direction, "panes": panes},
            "actions": [{"key": "O", "label": "Open card", "action": "node:open"}]}


def T(nid, status, title, summary, body="", priority="medium", assignee="agent", kind="task"):
    return {"id": nid, "type": kind, "status": status, "title": title, "summary": summary,
            "body": body, "priority": priority, "assignee": assignee}


SCENARIOS: list[dict] = []

# 1 ─ Backend / Fullstack ------------------------------------------------------------------------
SCENARIOS.append({
    "id": "feat_oauth", "name": "Feat-OAuth", "icon": "⛺", "biome": "void",
    "git": {"enabled": True, "mode": "worktree", "path": "./.orkcraft/worktrees/feat-oauth", "branch": "feat/oauth-flow"},
    "segment": "Backend / Fullstack developers",
    "story": "Isolated feature work with TDD and a generated PR",
    "nodes": [
        T("T2101", "in-progress", "OAuth: PKCE code exchange", "exchange code+verifier for tokens, rotate refresh",
          "## Description\nImplement `POST /oauth/token` with PKCE (S256).\n\n## Acceptance Criteria\n- [x] verifier 43–128 chars\n- [ ] refresh token rotation\n- [ ] revoke on reuse", "high"),
        T("T2102", "todo", "OAuth: refresh-token reuse detection", "revoke the whole family on reuse",
          "## Description\nA reused refresh token revokes its family (RFC 6819 §5.2.2.3).", "high"),
        T("T2103", "done", "OAuth: provider discovery (.well-known)", "cached for 1 h, ETag aware",
          "## Result\nDiscovery document cached; 3 providers configured."),
        T("T2104", "todo", "OAuth: consent screen copy", "scopes explained in plain words", priority="low", assignee="human"),
    ],
    "files": {
        "demo/feat_oauth/patch.md": """```diff
--- a/auth/token.py
+++ b/auth/token.py
@@ -41,12 +41,21 @@ def exchange_code(req: TokenRequest) -> TokenPair:
-    if req.code not in _codes:
-        raise InvalidGrant("unknown code")
+    grant = _codes.pop(req.code, None)
+    if grant is None:
+        raise InvalidGrant("unknown or used code")
+    if not verify_pkce(req.code_verifier, grant.challenge, method="S256"):
+        raise InvalidGrant("PKCE verification failed")
     access = mint_access(grant.user, scopes=grant.scopes, ttl=900)
-    refresh = mint_refresh(grant.user)
+    refresh = mint_refresh(grant.user, family=new_family())
     return TokenPair(access, refresh)
```
`auth/token.py` · +9 −3 · worktree `feat/oauth-flow`
""",
        "demo/feat_oauth/pytest.log": """============================= test session starts ==============================
collected 48 items

tests/test_discovery.py ........                                         [ 16%]
tests/test_pkce.py ..........                                            [ 37%]
tests/test_token.py ..........F.                                         [ 62%]
tests/test_refresh.py .......s...                                        [ 85%]
tests/test_revoke.py .......                                             [100%]

=================================== FAILURES ===================================
______________________ test_refresh_reuse_revokes_family _______________________
    def test_refresh_reuse_revokes_family(client):
        pair = login(client)
        rotate(client, pair.refresh)
>       assert rotate(client, pair.refresh).status_code == 401
E       assert 200 == 401
tests/test_token.py:88: AssertionError
=========================== short test summary info ============================
FAILED tests/test_token.py::test_refresh_reuse_revokes_family - assert 200 == 401
=================== 1 failed, 46 passed, 1 skipped in 3.41s ====================
""",
        "demo/feat_oauth/PR.md": """## feat(auth): OAuth 2.1 authorization code + PKCE

**What**
- `POST /oauth/token` exchanges code + verifier (S256 only)
- refresh tokens are issued in families and rotated on every use
- discovery documents cached for 1 h with ETag revalidation

**Tests** 46 passed · 1 skipped · 1 failing (reuse detection — T2102)

**Changelog**
- `feat(auth)`: PKCE code exchange
- `feat(auth)`: refresh token families
- `perf(auth)`: cached provider discovery
""",
    },
    "buildings": [
        building("oauth_forge", "Forge · Feature Worktree", "⚒️", "Smith", "senior coder, writes the feature",
                 {"tasks": nodes("feat_oauth"), "patch": file("demo/feat_oauth/patch.md")},
                 [pane("table", "tasks", "Feature board", 2, ["id", "title", "status"]), pane("markdown", "patch", "Working patch", 3)]),
        building("oauth_spire", "Scrying Spire · Diff Inspector", "🔮", "Shaman", "AST reviewer, reads the diff",
                 {"patch": file("demo/feat_oauth/patch.md")}, [pane("markdown", "patch", "Diff under review")]),
        building("oauth_lab", "Alchemy Lab · Test Runner", "🧪", "Alchemist", "TDD runner, loops the tests",
                 {"log": tail("demo/feat_oauth/pytest.log", 30)}, [pane("log", "log", "pytest --lf")]),
        building("oauth_vault", "Loot Chest · PR Vault", "📦", "Scribe", "release writer, PR text + changelog",
                 {"pr": file("demo/feat_oauth/PR.md")}, [pane("markdown", "pr", "PR draft")]),
    ],
    # (target, source, event, label, handler or None, filter)
    "roads": [
        ("oauth_spire", "oauth_forge", SEL, "on_patch", "reviewer", None),
        ("oauth_lab", "oauth_forge", TASK, "on_test_pass", "runner", None),
        ("oauth_vault", "oauth_spire", TASK, "on_approve", "writer", None),
    ],
    "handlers": {
        "oauth_spire": [{"name": "Reviewer", "kind": "agent", "harness": [ELDER], "role": "reviews every patch",
                         "orders": "Review the selected task's patch: risks, missing tests, naming.",
                         "sample": "**Review · T2101** (claude)\n- ✅ PKCE S256 only, verifier length checked\n- ⚠ `new_family()` is not persisted — reuse detection (T2102) cannot work yet\n- ⚠ no test for an expired code\n- nit: `InvalidGrant` messages leak whether a code existed"}],
        "oauth_lab": [{"name": "Runner", "kind": "chain", "role": "reruns the failing tests",
                       "chain": [{"op": "template", "md": "▶ `pytest --lf` rerun after: {title}\n\n{text}"}]}],
        "oauth_vault": [{"name": "Writer", "kind": "agent", "harness": [A, REVIEW], "role": "PR description + changelog",
                         "orders": "Write a conventional PR description and changelog from the approved review.",
                         "sample": "**PR ready** (agy wrote → claude reviewed)\n`feat(auth): OAuth 2.1 code + PKCE` · 3 commits · changelog updated"}],
    },
    "status": {("oauth_forge", "smith"): "busy", ("oauth_lab", "alchemist"): "alert"},
    "orders": {("oauth_lab", "alchemist"): "test_refresh_reuse_revokes_family fails: fix in Forge or mark xfail?"},
})

# 2 ─ QA & Automation --------------------------------------------------------------------------
SCENARIOS.append({
    "id": "qa_regression", "name": "QA-Regression", "icon": "🧪", "biome": "ice",
    "git": {"enabled": True, "mode": "worktree", "path": "./.orkcraft/worktrees/e2e-matrix", "branch": "test/e2e-matrix"},
    "segment": "QA & automation engineers",
    "story": "E2E tests synthesised from HAR logs, regression audit",
    "nodes": [
        T("T2201", "todo", "BUG-812 checkout 500 on promo code", "Sentry: 37 events in 1 h, Safari 17",
          "## HAR\n`POST /api/cart/promo` → 500 after 1.8 s\n\n## Repro\n1. add 2 items\n2. apply `AUTUMN25`\n3. pay", "high", "human"),
        T("T2202", "todo", "BUG-815 avatar upload hangs at 99%", "HAR: multipart stalls on the last chunk", priority="medium", assignee="human"),
        T("T2203", "in-progress", "BUG-799 flaky login redirect", "passes locally, fails 1/6 on CI", priority="medium"),
        T("T2204", "done", "BUG-790 cookie banner covers pay button", "fixed in 4.12.1; regression test added", priority="low"),
    ],
    "files": {
        "demo/qa_regression/playwright.log": """Running 24 tests using 4 workers

  ✓  1 checkout.spec.ts:12:5 › guest checkout (3.1s)
  ✓  2 checkout.spec.ts:31:5 › saved card (2.7s)
  ✘  3 checkout.spec.ts:48:5 › promo code AUTUMN25 (5.0s)
  ✓  4 profile.spec.ts:9:5 › change e-mail (1.9s)
  ✓  5 profile.spec.ts:27:5 › upload avatar (4.4s)
  -  6 login.spec.ts:18:5 › redirect after SSO (skipped: flaky, BUG-799)

  1) checkout.spec.ts:48:5 › promo code AUTUMN25
     Error: expect(received).toBe(expected)
     Expected: 200   Received: 500
       at checkout.spec.ts:61:34
     trace: test-results/checkout-promo/trace.zip

  1 failed · 1 skipped · 22 passed (41.6s)
""",
        "demo/qa_regression/trace.md": """### Trace · promo code AUTUMN25
| step | expected | actual |
|---|---|---|
| fill promo | `AUTUMN25` | `AUTUMN25` |
| click Apply | 200 · total −25 % | **500** · spinner |
| screenshot diff | 0.0 % | **4.7 %** (error toast) |

```diff
- Total: €74.25
+ Something went wrong. Try again.
```
""",
        "demo/qa_regression/repro.md": """## BUG-812 · repro pack
```bash
curl -X POST https://staging.shop.test/api/cart/promo \\
  -H 'Content-Type: application/json' -H 'Cookie: sid=…' \\
  -d '{"code":"AUTUMN25","cart":"c_91f2"}'
# → HTTP/1.1 500 · {"error":"DecimalException: quantize"}
```
Attached: `trace.zip`, `har/checkout-promo.har`, Allure report #412.
""",
    },
    "buildings": [
        building("qa_burrow", "Burrow · HAR / Bug Inbox", "🛖", "Peon", "log parser: Sentry, HAR, traffic dumps",
                 {"bugs": nodes("qa_regression")}, [pane("list", "bugs", "Incoming bugs")]),
        building("qa_ground", "Testing Ground · Playwright", "🧪", "Breaker", "QA lead, writes and runs repro scenarios",
                 {"log": tail("demo/qa_regression/playwright.log", 30)}, [pane("log", "log", "npx playwright test")]),
        building("qa_spire", "Spire · Trace & Snapshots", "🔮", "Inspector", "visual QA, diffs screenshots and traces",
                 {"trace": file("demo/qa_regression/trace.md")}, [pane("markdown", "trace", "Trace diff")]),
        building("qa_vault", "Loot Chest · Repro Vault", "📦", "Quartermaster", "packs a failing case into an issue",
                 {"repro": file("demo/qa_regression/repro.md")}, [pane("markdown", "repro", "Issue draft")]),
    ],
    "roads": [
        ("qa_ground", "qa_burrow", SEL, "on_new_log", "synth", {"node_type": ["task"], "node_status": ["todo", "in-progress"]}),
        ("qa_spire", "qa_ground", TASK, "on_failure", None, None),
        ("qa_vault", "qa_spire", TASK, "on_diff", "packer", None),
    ],
    "handlers": {
        "qa_ground": [{"name": "Synth", "kind": "agent", "harness": [A, REVIEW], "role": "HAR → Playwright spec",
                       "orders": "Turn the selected bug's HAR into a Playwright reproduction.",
                       "sample": "```ts\ntest('BUG-812 promo AUTUMN25', async ({ page }) => {\n  await addToCart(page, 2)\n  await page.fill('#promo', 'AUTUMN25')\n  await page.click('#apply-promo')\n  await expect(page.getByText('−25 %')).toBeVisible()\n})\n```"}],
        "qa_vault": [{"name": "Packer", "kind": "chain", "role": "issue template",
                      "chain": [{"op": "template", "md": "### Issue\n{text}\n\n_attach trace.zip · HAR · Allure_"}]}],
    },
    "status": {("qa_ground", "breaker"): "alert", ("qa_burrow", "peon"): "busy"},
    "orders": {("qa_ground", "breaker"): "Unknown selector `[data-test=promo-apply]` — use `#apply-promo`?"},
})

# 3 ─ Architects ------------------------------------------------------------------------------------
SCENARIOS.append({
    "id": "arch_core", "name": "Architecture-Core", "icon": "🏰", "biome": "forest",
    "git": {"enabled": True, "mode": "root", "path": "./", "branch": "main"},
    "segment": "Software & solution architects",
    "story": "Architecture drift, code audit, generated C4 / Mermaid",
    "nodes": [
        T("C2301", "active", "ADR-014 Payments talks to Ledger only via events", "no synchronous calls across the boundary",
          "## Decision\nPayments publishes `payment.settled`; Ledger consumes. No HTTP between them.", kind="context"),
        T("C2302", "active", "ADR-019 One writer per aggregate", "Orders owns order state; others read replicas", kind="context"),
        T("T2301", "todo", "Drift: payments → ledger HTTP call", "payments/settle.py:88 calls ledger.api directly", priority="high"),
        T("T2302", "todo", "Drift: search writes to orders table", "violates ADR-019", priority="medium"),
    ],
    "files": {
        "demo/arch_core/scan.log": """[scan] 412 modules · 9 services · 1 873 call edges
[scan] payments → ledger   HTTP  payments/settle.py:88      ✘ ADR-014
[scan] search   → orders   SQL   search/indexer.py:140      ✘ ADR-019
[scan] orders   → events   BUS   orders/outbox.py:22        ✓
[scan] ledger   ← events   BUS   ledger/consumer.py:17      ✓
[scan] cycles: 0 · new edges since main@a41c9e: 3
""",
        "demo/arch_core/c4.md": """```text
 ┌─────┐   ┌─────────────┐   ┌────────┐
 │ Web │──▶│ API Gateway │──▶│ Orders │◀──── Search (SQL ✘)
 └─────┘   └──────┬──────┘   └────────┘
                  ▼
            ┌──────────┐ payment.settled ┌────────┐
            │ Payments │ ─ ─ ─ ─ ─ ─ ─ ─▶│ Ledger │
            └──────────┘ ─── HTTP ✘ ────▶└────────┘
```
```mermaid
flowchart LR
  web[Web] --> api[API Gateway]
  api --> orders[Orders]
  api --> payments[Payments]
  payments -. payment.settled .-> ledger[Ledger]
  payments -->|HTTP ✘| ledger
  search[Search] -->|SQL ✘| orders
```
""",
        "demo/arch_core/wiki.md": """## Architecture wiki · synced to `docs/adr/`
- ADR-014 Payments ↔ Ledger via events — **2 violations open**
- ADR-019 One writer per aggregate — **1 violation open**
- C4 level 2 regenerated from `main@a41c9e`
""",
    },
    "buildings": [
        building("arch_altar", "Divination Altar · AST Crawler", "🔍", "Scout", "codebase auditor, call graph",
                 {"drift": nodes("arch_core", type="task"), "scan": tail("demo/arch_core/scan.log", 20)},
                 [pane("list", "drift", "Drift findings", 1), pane("log", "scan", "Call-graph scan", 1)]),
        building("arch_carto", "Cartographer · Mermaid", "🔮", "Scribe", "renders the architecture diagram",
                 {"c4": file("demo/arch_core/c4.md")}, [pane("markdown", "c4", "C4 · level 2")]),
        building("arch_hall", "Great Hall · ADR & RFC", "🏰", "Warlord", "enterprise architect, checks code against ADRs",
                 {"adrs": nodes("arch_core", type="context")}, [pane("table", "adrs", "Decisions", 1, ["id", "title", "status"])]),
        building("arch_wiki", "Loot Chest · Arch Wiki", "📦", "Quartermaster", "keeps docs/adr in sync",
                 {"wiki": file("demo/arch_core/wiki.md")}, [pane("markdown", "wiki", "docs/adr")]),
    ],
    "roads": [
        ("arch_carto", "arch_altar", SEL, "on_ast_scan", None, None),
        ("arch_hall", "arch_altar", SEL, "on_drift", "judge", {"node_type": ["task"]}),
        ("arch_wiki", "arch_carto", TASK, "on_export", None, None),
        ("arch_wiki", "arch_hall", TASK, "on_adr", "sync", None),
    ],
    "handlers": {
        "arch_hall": [{"name": "Judge", "kind": "agent", "harness": [ELDER], "role": "code vs ADRs",
                       "orders": "Which ADR does the selected drift violate, and what is the smallest fix?",
                       "sample": "**T2301 violates ADR-014.** Replace `ledger.api.post_entry()` in `payments/settle.py:88` with publishing `payment.settled`; Ledger already consumes it."}],
        "arch_wiki": [{"name": "Sync", "kind": "chain", "role": "wiki line per decision",
                       "chain": [{"op": "template", "md": "- {title} — updated from Great Hall"}]}],
    },
    "status": {("arch_altar", "scout"): "busy"},
})

# 4 ─ Product designers -----------------------------------------------------------------------------
SCENARIOS.append({
    "id": "design_review", "name": "Design-Review", "icon": "⛺", "biome": "forest",
    "git": {"enabled": False},
    "segment": "Product designers (UI/UX)",
    "story": "User-flow validation, edge states, UX copy review",
    "nodes": [
        T("T2401", "in-progress", "Onboarding · step 1 Welcome", "states: empty · loading · error · success", assignee="human"),
        T("T2402", "todo", "Onboarding · step 2 Connect bank", "error state needs retry + support link", assignee="human"),
        T("T2403", "todo", "Onboarding · step 3 First budget", "success state celebrates, no confetti overload", assignee="human"),
        T("T2404", "done", "Onboarding · step 0 Sign-up", "reviewed; WCAG AA contrast ok", assignee="human"),
    ],
    "files": {
        "demo/design_review/wireframe.md": """```text
┌──────────────────────────────────────┐
│  ◀  Connect your bank          2 / 3 │
├──────────────────────────────────────┤
│  ⚠  We couldn't reach ING right now. │
│                                      │
│   [ Try again ]   Choose another bank│
│                                      │
│   Need help? Chat with us →          │
└──────────────────────────────────────┘
   state: ERROR · focus → [ Try again ]
```""",
        "demo/design_review/copy.md": """### Connect bank · error
| tone | text |
|---|---|
| short | Couldn't connect. Try again? |
| friendly | Your bank isn't answering right now — give it another go in a moment. |
| technical | ING returned 503 (service unavailable). Retry or pick another bank. |

_Tone guide: brand-voice.md · "calm, no blame, one action"_
""",
        "demo/design_review/a11y.md": """### Heuristics & WCAG · step 2
- ✅ 1.4.3 contrast 7.1 : 1 on the error banner
- ⚠ 2.4.3 focus order jumps to the footer after *Try again*
- ⚠ Hick's law: 3 actions in the error state — keep 2
- ✅ Jakob's law: back arrow top-left, as in the rest of the app
""",
    },
    "buildings": [
        building("ds_loom", "Loom · User Flow", "🛖", "Weaver", "flow architect, state matrix per step",
                 {"flow": nodes("design_review")}, [pane("list", "flow", "Onboarding flow")]),
        building("ds_mirror", "Mirror · Wireframes", "🔮", "Artisan", "ASCII wireframes of each state",
                 {"wf": file("demo/design_review/wireframe.md")}, [pane("markdown", "wf", "Step 2 · error")]),
        building("ds_script", "Scriptorium · UX Copy", "📜", "Wordsmith", "three copy variants per state",
                 {"copy": file("demo/design_review/copy.md")}, [pane("markdown", "copy", "Copy variants")]),
        building("ds_watch", "Watchtower · a11y Auditor", "🗼", "Critic", "WCAG and heuristics",
                 {"a11y": file("demo/design_review/a11y.md")}, [pane("markdown", "a11y", "Audit")]),
    ],
    "roads": [
        ("ds_mirror", "ds_loom", SEL, "on_flow_step", None, None),
        ("ds_script", "ds_loom", SEL, "on_review", "copy_desk", None),
        ("ds_watch", "ds_mirror", TASK, "on_check", "heuristics", None),
    ],
    "handlers": {
        "ds_script": [{"name": "Copy Desk", "kind": "agent", "harness": [LABORER], "role": "copy in the brand voice",
                       "orders": "Three variants (short, friendly, technical) for each state of the selected step.",
                       "sample": "**Step 2 · loading** — short: *Connecting…* · friendly: *Saying hi to your bank…* · technical: *Waiting for ING (PSD2 consent)*"}],
        "ds_watch": [{"name": "Heuristics", "kind": "chain", "role": "checklist per wireframe",
                      "chain": [{"op": "template", "md": "☐ contrast · ☐ focus order · ☐ ≤ 2 actions — {title}"}]}],
    },
    "status": {("ds_script", "wordsmith"): "busy"},
})

# 5 ─ Design system -----------------------------------------------------------------------------------
SCENARIOS.append({
    "id": "design_tokens", "name": "Design-Tokens", "icon": "🧪", "biome": "void",
    "git": {"enabled": True, "mode": "worktree", "path": "./.orkcraft/worktrees/tokens-v2", "branch": "chore/tokens-v2"},
    "segment": "Design-system engineers & designers",
    "story": "Design-token sync (W3C / Style Dictionary) and versioned changes",
    "nodes": [
        T("T2501", "in-progress", "tokens v2: rename color.brand.primary", "→ color.accent.default (breaking)", priority="high"),
        T("T2502", "todo", "tokens v2: radius scale 4/8/12 → 4/6/10", "affects Button, Input, Card"),
        T("T2503", "done", "tokens v2: dark palette from Figma", "exported, 64 tokens", priority="low"),
    ],
    "files": {
        "demo/design_tokens/tokens.md": """```diff
 {
   "color": {
-    "brand": { "primary": { "$value": "#2F6FEB", "$type": "color" } },
+    "accent": { "default": { "$value": "#2F6FEB", "$type": "color" } },
     "surface": { "raised": { "$value": "#161B22", "$type": "color" } }
   },
   "radius": {
-    "md": { "$value": "8px", "$type": "dimension" }
+    "md": { "$value": "6px", "$type": "dimension" }
   }
 }
```""",
        "demo/design_tokens/mirror.md": """### Component mirror · after tokens v2
```text
 Button   ╭──────────────╮   radius 8 → 6
          │   Continue   │   bg  accent.default #2F6FEB
          ╰──────────────╯
 Input    ╭──────────────────────╮
          │ e-mail               │  border surface.raised
          ╰──────────────────────╯
```""",
        "demo/design_tokens/radar.log": """[radar] scanning 6 consumer repos for removed / renamed tokens
[radar] web-app        12 × --color-brand-primary   ✘ breaking
[radar] marketing-site  3 × --color-brand-primary   ✘ breaking
[radar] android         0                           ✓
[radar] ios             1 × BrandPrimary            ✘ breaking
[radar] admin           0                           ✓
[radar] docs            4 × color.brand.primary     ✘ breaking
[radar] blast radius: 4 repos · 20 references
""",
        "demo/design_tokens/migration.md": """## Migration guide · tokens v2
| old | new | codemod |
|---|---|---|
| `--color-brand-primary` | `--color-accent-default` | `npx ds-codemod rename-accent` |
| `--radius-md: 8px` | `--radius-md: 6px` | visual review only |

Exports: `tokens.css` · `tailwind.preset.js` · `tokens.d.ts` · `colors.xml`
""",
    },
    "buildings": [
        building("tk_foundry", "Token Foundry · JSON Sync", "⚒️", "Shaper", "token architect, Style Dictionary",
                 {"changes": nodes("design_tokens"), "diff": file("demo/design_tokens/tokens.md")},
                 [pane("table", "changes", "Token changes", 1, ["id", "title", "status"]), pane("markdown", "diff", "tokens.json", 2)]),
        building("tk_mirror", "Component Mirror · Sandbox", "🔮", "Mason", "component tester, previews the impact",
                 {"m": file("demo/design_tokens/mirror.md")}, [pane("markdown", "m", "Preview")]),
        building("tk_radar", "Radar · Consumer Repos", "🗼", "Lookout", "static audit of consumers",
                 {"r": tail("demo/design_tokens/radar.log", 20)}, [pane("log", "r", "Blast radius")]),
        building("tk_loot", "Loot Chest · Exports", "📦", "Quartermaster", "migration guide + artifacts",
                 {"g": file("demo/design_tokens/migration.md")}, [pane("markdown", "g", "Migration guide")]),
    ],
    "roads": [
        ("tk_mirror", "tk_foundry", SEL, "on_token_change", None, None),
        ("tk_loot", "tk_foundry", TASK, "on_compile", "exporter", None),
        ("tk_radar", "tk_mirror", TASK, "on_impact", "scanner", None),
    ],
    "handlers": {
        "tk_loot": [{"name": "Exporter", "kind": "chain", "role": "CSS / Tailwind / TS / Android",
                     "chain": [{"op": "template", "md": "exported {title}: tokens.css · tailwind.preset.js · tokens.d.ts · colors.xml"}]}],
        "tk_radar": [{"name": "Scanner", "kind": "hybrid", "harness": [LABORER], "role": "grep consumers, escalate breaking",
                      "script": {"path": ".orkcraft/scripts/tk-radar-scanner.py"},
                      "sample": "**Breaking:** 4 repos · 20 references to `color.brand.primary` → escalated to claude for the migration plan"}],
    },
    "status": {("tk_foundry", "shaper"): "busy"},
})

# 6 ─ Product managers ------------------------------------------------------------------------------
SCENARIOS.append({
    "id": "strategy_sprint", "name": "Strategy-Sprint", "icon": "🏰", "biome": "forest",
    "git": {"enabled": False},
    "segment": "Product managers",
    "story": "User pains triage, feature scoping, user stories",
    "nodes": [
        T("C2601", "active", "Cluster: exports are painful (23 quotes)", "CSV breaks in Excel, no PDF", kind="context"),
        T("C2602", "active", "Cluster: onboarding too long (17 quotes)", "7 steps, users drop at step 4", kind="context"),
        T("C2603", "active", "Cluster: team sharing (9 quotes)", "read-only links requested", kind="context"),
        T("T2601", "todo", "PRD: one-click export", "problem, metrics, hypotheses", priority="high", assignee="human"),
    ],
    "files": {
        "demo/strategy_sprint/prd.md": """## PRD · One-click export
**Problem** 23 of 140 interviewees export monthly; 61 % hit broken CSV encodings.
**Success metrics** export completion ≥ 95 % · support tickets on export −50 % in 60 days
**Hypotheses**
1. UTF-8 BOM + locale-aware separators fix most Excel breakage
2. A PDF summary replaces 70 % of manual screenshots
""",
        "demo/strategy_sprint/stories.md": """```gherkin
Feature: One-click export
  Scenario: Excel-friendly CSV
    Given a user with transactions in EUR
    When they choose "Export → CSV (Excel)"
    Then the file opens in Excel with correct accents and columns

  Scenario: PDF summary
    Given a month with at least one transaction
    When they choose "Export → PDF"
    Then a one-page summary with totals per category is downloaded
```""",
        "demo/strategy_sprint/vault.md": """## PRD vault
- PRD · One-click export — _draft 3_, 2 stories, 6 AC
- PRD · Short onboarding — _idea_
- Market notes · 4 competitors export PDF, 1 exports XLSX
""",
    },
    "buildings": [
        building("pm_post", "Listening Post · Feedback", "🛖", "Peon", "sifts interviews, tickets and reviews",
                 {"clusters": nodes("strategy_sprint", type="context")}, [pane("list", "clusters", "Pain clusters")]),
        building("pm_hall", "Great Hall · PRD Drafter", "🏰", "Warlord", "product strategist",
                 {"prd": file("demo/strategy_sprint/prd.md")}, [pane("markdown", "prd", "PRD draft")]),
        building("pm_forge", "Forge · Story Slicer", "⚒️", "Smith", "backlog groomer, Gherkin AC",
                 {"s": file("demo/strategy_sprint/stories.md")}, [pane("markdown", "s", "User stories")]),
        building("pm_vault", "Loot Chest · PRD Vault", "📦", "Quartermaster", "specs for the wiki",
                 {"v": file("demo/strategy_sprint/vault.md")}, [pane("markdown", "v", "Vault")]),
    ],
    "roads": [
        ("pm_hall", "pm_post", SEL, "on_cluster", "strategist", {"node_type": ["context"]}),
        ("pm_forge", "pm_hall", TASK, "on_spec_ready", "slicer", None),
        ("pm_vault", "pm_forge", TASK, "on_stories_done", "indexer", None),
    ],
    "handlers": {
        "pm_hall": [{"name": "Strategist", "kind": "agent", "harness": [ELDER], "role": "problem statement + metrics",
                     "orders": "Draft a problem statement, success metrics and 2 hypotheses from the selected cluster.",
                     "sample": "**Exports** — 23 quotes → problem: monthly export breaks in Excel for 61 %. Metric: completion ≥ 95 %. H1: UTF-8 BOM; H2: PDF summary."}],
        "pm_forge": [{"name": "Slicer", "kind": "agent", "harness": [A, REVIEW], "role": "stories in Gherkin",
                      "orders": "Slice the PRD into user stories with Given/When/Then acceptance criteria.",
                      "sample": "2 stories · 6 acceptance criteria (agy sliced → claude checked for testability)"}],
        "pm_vault": [{"name": "Indexer", "kind": "chain", "role": "one vault line per spec",
                      "chain": [{"op": "template", "md": "- {text} — filed to the PRD vault"}]}],
    },
    "status": {("pm_hall", "warlord"): "busy"},
})

# 7 ─ Delivery leads ----------------------------------------------------------------------------------
SCENARIOS.append({
    "id": "delivery_control", "name": "Delivery-Control", "icon": "🗺️", "biome": "forest",
    "git": {"enabled": True, "mode": "root", "path": "./", "branch": "main"},
    "segment": "Project managers & technical delivery leads",
    "story": "Blockers, branches and release reports end to end",
    "nodes": [
        T("T2701", "in-progress", "feat/oauth-flow · review waiting 2 d", "blocked on security review", priority="high"),
        T("T2702", "in-progress", "test/e2e-matrix · CI red 6 h", "flaky login redirect", priority="high"),
        T("T2703", "todo", "chore/tokens-v2 · 4 consumer repos break", "needs migration window"),
        T("T2704", "done", "release 4.12.1 shipped", "cookie banner fix"),
    ],
    "files": {
        "demo/delivery_control/radar.log": """[health] feat/oauth-flow     ahead 14 · CI ✓ · review ⏳ 2d      ❓ blocked
[health] test/e2e-matrix     ahead 6  · CI ✘ 6h (login.spec)     ❓ red
[health] chore/tokens-v2     ahead 9  · CI ✓ · 4 consumers ✘     ⚠ breaking
[health] feat/stripe-billing ahead 22 · CI ✓ · deploy staging ✓  ✓
[health] deadlines: release 4.13 in 3 days · 2 blockers open
""",
        "demo/delivery_control/chronicle.log": """09:02 ⚒ Smith      T2701 → in-progress
09:40 🧪 Alchemist  test_refresh_reuse… failed (❓)
10:15 🔮 Shaman     review requested on feat/oauth-flow
11:03 🧪 Breaker    selector question on promo spec (❓)
12:30 📦 Scribe     PR draft updated
13:10 🗼 Lookout    4 consumer repos break on tokens v2
""",
        "demo/delivery_control/brief.md": """## Weekly status · week 40
**Shipped** 4.12.1 (cookie banner fix)
**On track** stripe billing (staging green)
**At risk** OAuth (security review 2 d), e2e matrix (CI red 6 h)
**Decisions needed** migration window for tokens v2 (4 repos)
_Generated from Chronicles — no status meeting needed._
""",
    },
    "buildings": [
        building("dc_watch", "War Watchtower · Health Radar", "🗼", "Overseer", "branches, deadlines, stuck CI",
                 {"h": tail("demo/delivery_control/radar.log", 20)}, [pane("log", "h", "Branch health")]),
        building("dc_board", "War Board · Multi-Worktree", "⚒️", "Smith", "one board across worktrees",
                 {"items": nodes("delivery_control")}, [pane("table", "items", "Across orkspaces", 1, ["id", "title", "status"])]),
        building("dc_chron", "Chronicles · Velocity Audit", "📜", "Chronicler", "who changed what, when",
                 {"c": tail("demo/delivery_control/chronicle.log", 30)}, [pane("log", "c", "Audit stream")]),
        building("dc_loot", "Loot Chest · Release Brief", "📦", "Herald", "weekly report, no pinging people",
                 {"b": file("demo/delivery_control/brief.md")}, [pane("markdown", "b", "Weekly brief")]),
    ],
    "roads": [
        ("dc_board", "dc_watch", TASK, "on_blocker", None, None),
        ("dc_loot", "dc_watch", TASK, "on_digest", "herald_desk", None),
        ("dc_chron", "dc_board", SEL, "on_resolved", "auditor", None),
        ("dc_loot", "dc_chron", TASK, "on_log", None, None),
    ],
    "handlers": {
        "dc_loot": [{"name": "Herald Desk", "kind": "agent", "harness": [LABORER], "role": "weekly status from chronicles",
                     "orders": "Write the weekly status: shipped, on track, at risk, decisions needed.", "run": {"quiet_s": 60},
                     "sample": "**Week 40** · shipped 4.12.1 · at risk: OAuth review (2 d), e2e CI red (6 h) · decide: tokens v2 migration window"}],
        "dc_chron": [{"name": "Auditor", "kind": "chain", "role": "audit line per change",
                      "chain": [{"op": "template", "md": "{id} · {status} · {title}"}]}],
    },
    "status": {("dc_watch", "overseer"): "alert", ("dc_chron", "chronicler"): "busy"},
    "orders": {("dc_watch", "overseer"): "OAuth review stuck for 2 days — escalate to security lead?"},
})

# 8 ─ Indie developers -------------------------------------------------------------------------------
SCENARIOS.append({
    "id": "solo_saas", "name": "Solo-SaaS", "icon": "⛺", "biome": "void",
    "git": {"enabled": True, "mode": "worktree", "path": "./.orkcraft/worktrees/stripe-billing", "branch": "feat/stripe-billing"},
    "segment": "Indie developers & solo founders",
    "story": "Ship a feature alone — from backend to the launch post",
    "nodes": [
        T("T2801", "in-progress", "Stripe: checkout session + webhooks", "idempotent webhook handler", priority="high"),
        T("T2802", "todo", "Stripe: customer portal link", "manage / cancel subscription"),
        T("T2803", "done", "Prisma: subscriptions table", "migration 0007 applied on staging"),
    ],
    "files": {
        "demo/solo_saas/diff.md": """```diff
+model Subscription {
+  id         String   @id @default(cuid())
+  userId     String   @unique
+  stripeId   String   @unique
+  status     SubStatus
+  renewsAt   DateTime
+}
+
+export async function POST(req: Request) {
+  const event = stripe.webhooks.constructEvent(await req.text(), sig, secret)
+  if (await seen(event.id)) return ok()          // idempotent
+  await applySubscriptionEvent(event)
+}
```""",
        "demo/solo_saas/launch.md": """## Launch pack · Billing is live
**Release notes** Plans, trials and a self-serve portal — powered by Stripe.
**Show HN** "I built billing for my budgeting app in a weekend — here's the webhook design"
**Product Hunt tagline** Budgets that pay for themselves. Now with Pro.
""",
        "demo/solo_saas/uptime.log": """14:00:02 GET  /api/health           200  12ms
14:00:31 POST /api/stripe/webhook   200  41ms  evt_1PqA…
14:01:07 POST /api/stripe/webhook   200  38ms  evt_1PqB… (duplicate, skipped)
14:02:44 GET  /app/billing          200  96ms
14:03:10 POST /api/checkout         500 812ms  StripeInvalidRequest: price_… missing
14:03:11 ALERT 500 on /api/checkout (1 in 5 min)
""",
        "demo/solo_saas/vault.md": """## Vault
- `migrations/0007_subscriptions.sql`
- `seo/billing-landing.md` (1 200 words)
- `infra/stripe-webhook.env.example`
""",
    },
    "buildings": [
        building("solo_forge", "Forge · Fullstack Dev", "⚒️", "Smith", "fullstack partner: schema, API, UI",
                 {"tasks": nodes("solo_saas"), "d": file("demo/solo_saas/diff.md")},
                 [pane("table", "tasks", "Billing", 1, ["id", "title", "status"]), pane("markdown", "d", "feat/stripe-billing", 2)]),
        building("solo_growth", "Growth Lab · Marketing Copy", "🧪", "Marketer", "release notes, HN, Product Hunt",
                 {"l": file("demo/solo_saas/launch.md")}, [pane("markdown", "l", "Launch copy")]),
        building("solo_sentry", "Sentry Post · Uptime & Logs", "🗼", "Lookout", "watches production logs",
                 {"u": tail("demo/solo_saas/uptime.log", 20)}, [pane("log", "u", "production")]),
        building("solo_loot", "Loot Chest · Launch Pack", "📦", "Quartermaster", "SEO texts, migrations, configs",
                 {"v": file("demo/solo_saas/vault.md")}, [pane("markdown", "v", "Vault")]),
    ],
    "roads": [
        ("solo_growth", "solo_forge", TASK, "on_ship", "copywriter", None),
        ("solo_sentry", "solo_forge", TASK, "on_deploy", "watch", None),
        ("solo_loot", "solo_growth", TASK, "on_publish", None, None),
    ],
    "handlers": {
        "solo_growth": [{"name": "Copywriter", "kind": "agent", "harness": [A, REVIEW], "role": "launch copy from the diff",
                         "orders": "Release notes, a Show HN title and a Product Hunt tagline from the shipped diff.",
                         "sample": "**Show HN:** Billing for my budgeting app in a weekend — idempotent Stripe webhooks explained"}],
        "solo_sentry": [{"name": "Watch", "kind": "chain", "role": "500s → alert line",
                         "chain": [{"op": "filter", "field": "text", "cmp": "contains", "value": "500"},
                                   {"op": "template", "md": "🚨 {text}"}]}],
    },
    "status": {("solo_forge", "smith"): "busy", ("solo_sentry", "lookout"): "alert"},
    "orders": {("solo_sentry", "lookout"): "500 on /api/checkout: price id missing in prod env — roll back?"},
})

# ─ The managers' sandbox (orkcraft --demo --demo-set managers) ──────────────────────────────────────
# Its own Town Scroll: the main sandbox already fills F1–F8.

MANAGER_SCENARIOS: list[dict] = []

# Engineering manager · 1on1 prep: calendar, e-mail and Jira activity feed one prefilled 1on1 note.
MANAGER_SCENARIOS.append({
    "id": "one_on_one", "name": "1on1-Prep", "icon": "👥", "biome": "forest",
    "git": {"enabled": False},
    "segment": "Engineering managers",
    "story": "A prefilled 1on1: calendar, e-mail and Jira activity flow into one note",
    # the note on the left, the three sources stacked on the right
    "layout": [(0.0, 0.0, 0.56, 1.0), (0.62, 0.0, 0.38, 0.30), (0.62, 0.35, 0.38, 0.30), (0.62, 0.70, 0.38, 0.30)],
    "nodes": [
        T("T3101", "todo", "Thu 10:00 · 1on1 with Alex Kim (30 min)", "biweekly · Zoom · agenda doc attached", assignee="human"),
        T("T3102", "todo", "Thu 14:00 · Sprint 41 planning", "Alex presents the payments spike", assignee="human"),
        T("T3103", "todo", "Fri 11:00 · Calibration pre-read", "H2 review cycle", assignee="human", priority="low"),
        T("T3111", "todo", "Alex Kim: PTO 14–18 Oct", "asks to move the on-call week", assignee="human"),
        T("T3112", "todo", "PM (Dana): payments spike slipped again", "\"Is Alex overloaded?\"", assignee="human", priority="high"),
        T("T3113", "todo", "HR: review cycle opens Monday", "self-reviews due 21 Oct", assignee="human", priority="low"),
        T("T3121", "done", "PAY-412 idempotent refunds", "done Tue · 5 pts · 2 review rounds", assignee="alex"),
        T("T3122", "in-progress", "PAY-431 payments spike (3DS2)", "in progress 9 days · blocked on vendor sandbox", assignee="alex", priority="high"),
        T("T3123", "in-progress", "OPS-77 on-call: 6 pages this week", "3 at night · 2 false alarms", assignee="alex"),
        T("T3124", "todo", "PAY-440 refund reports", "not started · 3 pts", assignee="alex", priority="low"),
    ],
    "files": {
        "demo/one_on_one/alex-kim.md": """# 1on1 · Alex Kim · Thu 10:00
_prefilled by Orkcraft from Calendar, Mail and Jira — edit before the meeting_

## Since last time (2 weeks)
| week | done | in progress | notes |
|---|---|---|---|
| 39 | PAY-398, PAY-405 (8 pts) | — | smooth |
| 40 | PAY-412 (5 pts) | PAY-431 | 2 review rounds on refunds |
| 41 | — | PAY-431 (day 9), OPS-77 | on-call heavy |

## Capacity
- Sprint 41: **13 / 21 pts** committed · velocity trend ↓ (21 → 13 → 5)
- On-call this week: **6 pages**, 3 at night
- PTO **14–18 Oct** → 4 working days next sprint

## Problems & signals
- ⚠ PAY-431 blocked 9 days on the vendor's 3DS2 sandbox
- ⚠ PM asks whether Alex is overloaded (mail, Tue)
- ⚠ Night pages: 2 of 6 were false alarms (alert tuning?)

## Agenda
1. How are you? Energy after the on-call week
2. PAY-431: unblock or re-scope — who can talk to the vendor?
3. Move on-call away from the PTO week
4. Growth: owning the payments design review

## Action items from last time
- [x] Alex: pair with Sam on refunds
- [ ] Me: ask SRE to tune the payment alerts
""",
    },
    "buildings": [
        building("em_note", "Scrying Spire · 1on1 Note", "🔮", "Shaman", "keeps the 1on1 note up to date",
                 {"note": file("demo/one_on_one/alex-kim.md")}, [pane("markdown", "note", "alex-kim.md", 3)],
                 direction="vertical"),
        building("em_calendar", "Watchtower · Calendar", "🗼", "Lookout", "your week, meetings with context",
                 {"events": nodes("one_on_one_cal")}, [pane("list", "events", "This week")]),
        building("em_mail", "Farm · Mail", "🛖", "Peon", "mail that matters for your people",
                 {"mail": nodes("one_on_one_mail")}, [pane("list", "mail", "Inbox · flagged")]),
        building("em_jira", "Forge · Jira: Alex Kim", "⚒️", "Smith", "one person's Jira activity",
                 {"issues": nodes("one_on_one_jira")}, [pane("table", "issues", "Alex · last 14 days", 1, ["id", "title", "status"])]),
    ],
    "roads": [
        ("em_note", "em_calendar", SEL, "on_meeting", "agenda", None),
        ("em_note", "em_mail", SEL, "on_mail", "agenda", None),
        ("em_note", "em_jira", SEL, "on_jira_activity", "agenda", None),
    ],
    "handlers": {
        "em_note": [
            {"name": "Agenda", "kind": "chain", "role": "one line per source, rerun on every new event",
             "chain": [{"op": "template", "md": "- {title} · _{status}_"}, {"op": "join", "sep": "\n"}]},
            {"name": "Coach", "kind": "agent", "harness": [WARRIOR], "role": "talking points for the 1on1",
             "orders": "From the latest meeting, mail and Jira activity, suggest three talking points and one risk.",
             "sample": "**Talking points** (claude)\n1. On-call load: 6 pages, 3 at night — offer to swap the PTO week\n2. PAY-431 blocked 9 days: unblock via vendor contact or re-scope\n3. Growth: payments design review ownership\n\n**Risk:** velocity 21 → 13 → 5 while the PM already asks about overload"},
        ],
    },
    "status": {("em_note", "shaman"): "busy", ("em_jira", "smith"): "alert"},
    "orders": {("em_jira", "smith"): "PAY-431 blocked 9 days — raise it in the 1on1?"},
})

# The three sources of the 1on1 read different slices of the graph: tag them apart.
for _n in MANAGER_SCENARIOS[0]["nodes"]:
    _n["tag"] = {"T310": "one_on_one_cal", "T311": "one_on_one_mail", "T312": "one_on_one_jira"}[_n["id"][:4]]

from orkcraft.demo.dashboard import DASHBOARD_SCENARIOS  # noqa: E402  (typed buildings, T1105)

SETS = {"main": SCENARIOS, "managers": MANAGER_SCENARIOS, "dashboard": DASHBOARD_SCENARIOS}


# -- huts: how every showcase building looks collapsed on the town map -------------------

def mini(art: str, *lines: tuple) -> dict:
    """`(data, template)` or `(data, template, where)` per status line."""
    return {"art": art, "lines": [{"data": ln[0], "template": ln[1], **({"where": ln[2]} if len(ln) > 2 else {})}
                                  for ln in lines]}


IN_WORK, TODO = {"status": "in-progress"}, {"status": "todo"}
MINI: dict[str, dict] = {
    "oauth_forge": mini("forge", ("tasks", "⚙ {count} · {title}", IN_WORK), ("tasks", "{count} todo · next {id}", TODO)),
    "oauth_spire": mini("spire", ("patch", "{last}")),
    "oauth_lab": mini("workshop", ("log", "{last}")),
    "oauth_vault": mini("vault", ("pr", "{heading}")),
    "qa_burrow": mini("burrow", ("bugs", "🐞 {count} · {title}")),
    "qa_ground": mini("workshop", ("log", "{last}")),
    "qa_spire": mini("spire", ("trace", "{heading}")),
    "qa_vault": mini("vault", ("repro", "{heading}")),
    "arch_altar": mini("mill", ("scan", "{last}"), ("drift", "⚠ {count} drift · {title}")),
    "arch_carto": mini("library", ("c4", "🗺 C4 · {count} lines")),
    "arch_hall": mini("great_hall", ("adrs", "📜 {count} · {title}")),
    "arch_wiki": mini("library", ("wiki", "{heading}")),
    "ds_loom": mini("workshop", ("flow", "🧵 {count} · {title}")),
    "ds_mirror": mini("spire", ("wf", "🪞 wireframe · {count} lines")),
    "ds_script": mini("library", ("copy", "{heading}")),
    "ds_watch": mini("watchtower", ("a11y", "{heading}"), ("a11y", "{last}")),
    "tk_foundry": mini("forge", ("changes", "🧪 {count} · {title}")),
    "tk_mirror": mini("spire", ("m", "{heading}")),
    "tk_radar": mini("watchtower", ("r", "{last}")),
    "tk_loot": mini("vault", ("g", "{heading}")),
    "pm_post": mini("rookery", ("clusters", "📨 {count} · {title}")),
    "pm_hall": mini("great_hall", ("prd", "{heading}")),
    "pm_forge": mini("forge", ("s", "📋 stories · {count} lines")),
    "pm_vault": mini("vault", ("v", "{heading}"), ("v", "{last}")),
    "dc_watch": mini("watchtower", ("h", "{last}")),
    "dc_board": mini("barracks", ("items", "{count} streams · {title}")),
    "dc_chron": mini("mill", ("c", "{last}")),
    "dc_loot": mini("vault", ("b", "{heading}")),
    "solo_forge": mini("forge", ("tasks", "⚙ {count} · {title}", IN_WORK), ("tasks", "{count} todo", TODO)),
    "solo_growth": mini("rookery", ("l", "{heading}")),
    "solo_sentry": mini("watchtower", ("u", "{last}")),
    "solo_loot": mini("vault", ("v", "{heading}")),
    "em_note": mini("spire", ("note", "{heading}")),
    "em_calendar": mini("watchtower", ("events", "{title}"), ("events", "{count} this week")),
    "em_mail": mini("rookery", ("mail", "📨 {count} · {title}")),
    "em_jira": mini("forge", ("issues", "{count} issues · {title}")),
}
for _sc in SCENARIOS + MANAGER_SCENARIOS:
    for _b in _sc["buildings"]:
        _b["mini"] = MINI[_b["id"]]
