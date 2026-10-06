# Design — 🪙 Codex: its limits and its spend

Status: design notes, written 2026-10-06. §5.1 (the ⏳ Limits row) is built
(`orkcraft/quota/codex_quota.py`): the plain `codex` bucket's rows are `5h` / `weekly`, another bucket
names itself with its window (`gpt-6-astra 5h`), and the plan, credits and `as of` go into the row's
`note`, so each window keeps its own name on the Tally Crag. §5.2 (pricing) is not built.
Answers the roadmap item "🪙 Codex: its limits and its spend" (`docs/roadmap.md`).

Codex sources were read at `openai/codex` main, commit `685270a` (2026-10-05); the newest stable
tag then was `rust-v0.160.1`, and orkcraft's tests pin `codex-cli 0.160.0`. Links below point at
that commit: `C/` stands for `https://github.com/openai/codex/blob/685270a56a96c76ae5b0853373a19d6ed5bc6fd4/`.
**✓** = read in the source or a page; **?** = not verified (say so wherever it is used).

## 1. Short answer

- **Limits: yes.** Codex answers its plan's windows over JSON-RPC (`codex app-server`,
  method `account/rateLimits/read`) without running a model turn. Its own TUI `/status` uses the
  same call. Session files carry the same snapshot after every turn, so they are a free fallback.
- **Spend: yes for an API key, as an estimate for a ChatGPT login.** Codex runs ordinary OpenAI
  API models (`gpt-6-astra`, `gpt-6.1-sol`, `gpt-6-luna`, …), and `codex exec --json` gives
  input, cached input and output tokens. The per-token prices could not be read first-hand from
  this machine (openai.com is blocked by the egress proxy); the numbers in §4 are from search
  snippets and must be checked before they go into `PRICES`.

## 2. Where the windows can be read

| Source | What it gives | Spends quota? | Versions |
|---|---|---|---|
| `codex app-server` → `account/rateLimits/read` | primary + secondary window: `usedPercent`, `windowDurationMins`, `resetsAt` (unix s); `planType`; credits; per-`limitId` buckets | no model turn — one GET to the ChatGPT backend (`/wham/usage` or `/api/codex/usage`) ✓ | absent in 0.50.0, present from 0.53.0 ✓ (bisected by tag, see below) |
| Session rollouts `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<thread>.jsonl` (`.jsonl.zst` when compression is on) | `event_msg` / `token_count` lines with `payload.rate_limits` (same snapshot) and `payload.info` (token usage) | no — a file read; but only as fresh as the last turn | `rate_limits` on `token_count` from ≤0.46.0 on ✓; shapes changed (below) |
| `/status` in the Codex TUI | the same windows, drawn | no | interactive only — not scriptable |
| sqlite store `~/.codex/state_5.sqlite`, `thread_history_1.sqlite` | `threads.tokens_used` (one total), turns and items; **no rate limits** | — | useless for limits ✓ |
| `codex exec --json` | `thread.started`, `turn.*`, `item.*`, `error`; `turn.completed.usage` | — | **no rate limits, no model name** ✓ |

Evidence:

- Method and response: `account/rateLimits/read` → `GetAccountRateLimitsResponse { rateLimits,
  rateLimitsByLimitId, ordinaryUsageAllowed, … }`; `RateLimitSnapshot { primary, secondary,
  credits, planType, rateLimitReachedType, … }`; `RateLimitWindow { usedPercent, windowDurationMins,
  resetsAt }` — ✓ `C/codex-rs/app-server-protocol/src/protocol/common.rs` (line ~1327),
  `C/codex-rs/app-server-protocol/src/protocol/v2/account.rs` (lines 315–345, 664–758).
- It refuses an API-key login: "chatgpt authentication required to read rate limits" — ✓
  `C/codex-rs/app-server/src/request_processors/account_processor.rs` (line ~1202). An API-key
  Codex has no plan windows; its limits are the API org's, which Codex does not report.
- The backend URLs: ✓ `C/codex-rs/backend-client/src/client/rate_limit_resets.rs` (line ~126).
- The handshake a client sends first: `initialize` with `clientInfo {name, title, version}`, then
  the `initialized` notification — ✓ `C/codex-rs/app-server-test-client/src/lib.rs` (line ~1749).
- `/status` calls the same method — ✓ `C/codex-rs/tui/src/app/background_requests.rs` (line ~815).
- `token_count` is still persisted to rollouts — ✓ `C/codex-rs/rollout/src/policy.rs` (line ~133);
  `TokenCountEvent { info, rate_limits }` — ✓ `C/codex-rs/protocol/src/protocol.rs` (line ~2343).
  Sessions dir: ✓ `C/codex-rs/rollout/src/lib.rs` (`SESSIONS_SUBDIR`), year/month/day folders
  ✓ `C/codex-rs/rollout/src/recorder.rs`; `.jsonl.zst` ✓ `C/codex-rs/rollout/src/compression.rs`
  (the feature `local_thread_store_compression` is off by default ✓ `C/codex-rs/features/src/lib.rs`).
- sqlite file names ✓ `C/codex-rs/state/src/sqlite.rs` (lines 34–39); `threads` ✓
  `C/codex-rs/state/migrations/0001_threads.sql`; history tables ✓
  `C/codex-rs/state/thread_history_migrations/0001_thread_history.sql`. The sqlite store is a
  projection of the rollout files, which still exist (`thread_history_projection_state.
  next_rollout_byte_offset`).
- `exec --json` events ✓ `C/codex-rs/exec/src/exec_events.rs`.
- Version bisection: `raw.githubusercontent.com/openai/codex/rust-v<tag>/codex-rs/app-server-protocol/src/protocol/common.rs`
  contains `account/rateLimits/read` at 0.53.0, 0.60.1, 0.100.0, 0.160.0 and not at 0.50.0 ✓.

Older `rate_limits` shapes a rollout parser meets (✓ from tag sources and
`C/codex-rs/thread-store/src/local/rollout_migration/line_parser.rs`):

| Era | Shape |
|---|---|
| ~0.40 | flat: `primary_used_percent`, `secondary_used_percent`, `primary_window_minutes`, … |
| later | `primary` / `secondary` objects: `used_percent`, `window_minutes`, `resets_in_seconds` ? |
| later | `resets_at` as an RFC 3339 string (the migration rewrites it) |
| now | `resets_at` as unix seconds; `limit_id`, `plan_type`, `credits` added |

## 3. Telling the billing mode

`codex login status` prints one line on **stderr** and exits 0 when logged in ✓
(`C/codex-rs/cli/src/login.rs`, line ~447): `Logged in using ChatGPT` (subscription) or
`Logged in using an API key - sk-…` (masked) — plus access-token, personal-token and Bedrock variants.
It reads the auth store, no network call, no model turn.

Two things in `orkcraft/tools.py` `_codex_login` are wrong against that source:

- `~/.codex/auth.json` being there does **not** mean a subscription: `codex login --with-api-key`
  writes the key into the same file (`AuthDotJson { auth_mode, OPENAI_API_KEY, tokens }`, ✓
  `C/codex-rs/login/src/auth/storage.rs`).
- `OPENAI_API_KEY` in the environment does not make Codex API-billed; `codex exec` honours
  `CODEX_API_KEY` (`enable_codex_api_key_env: true`, ✓ `C/codex-rs/exec/src/lib.rs` ~745), while
  `OPENAI_API_KEY` only pre-fills the TUI onboarding ✓ (`C/codex-rs/tui/src/onboarding/auth.rs`).

Keep the "never read auth.json" rule: run `codex login status` and match the first words.

## 4. Prices

Codex's bundled model list uses the API names: `gpt-6-astra`, `gpt-6-sol`, `gpt-6.1-sol`,
`gpt-6-luna`, `gpt-5.6-*`, `gpt-5.5` ✓ (`C/codex-rs/models-manager/models.json`). orkcraft's tiers
already use three of them (`orkcraft/realm/tiers.py`).

What a web search restricted to openai.com domains returned for
<https://developers.openai.com/api/docs/pricing> — **?, not fetched** (openai.com,
developers.openai.com, platform.openai.com and help.openai.com are blocked here); $/1M tokens,
standard tier, short context:

| Model | Input | Cached input | Cache write | Output | Long-context (in / cached / out) |
|---|---|---|---|---|---|
| gpt-6-astra | 10.00 | 1.00 | 12.50 | 50.00 | 20.00 / 2.00 / 75.00 |
| gpt-6.1-sol | 2.00 | 0.10 | 2.50 | 10.00 | 4.00 / 0.20 / 15.00 |
| gpt-6-luna | 0.10 | 0.01 | 0.125 | 0.50 | 0.20 / 0.02 / 0.75 |

Not found at all: `gpt-6-sol`, `gpt-5.6-*`, the long-context threshold, and whether cache writes
are billed separately for every model. A third-party page (pricepertoken.com) gave a different
astra price ($5 / $0.50 / $25), so these numbers are not to be trusted until a person reads the
OpenAI page and writes the date next to them, as `pricing.py` does for Claude.

Billing modes:

- **API key** — tokens are billed at the API rates; pricing a run is a real cost.
- **ChatGPT login** — the plan pays; a run uses the 5-hour / weekly windows and, past them,
  credits. A per-token price is then an **API-equivalent estimate**, exactly like Claude Pro/Max in
  `pricing.py`'s docstring. The ChatGPT backend also has per-turn estimates in USD
  (`/wham/usage/thread-estimates/query`, `estimated_usage_usd_micros`, ✓
  `C/codex-rs/backend-client/src/client/chatgpt_turn_cost.rs`), but that is an internal endpoint
  for workspace members (?) — not a source to build on.

## 5. The plan

### 5.1 ⏳ Limits: a `codex` row

1. **`orkcraft/quota/codex_quota.py`** (new, next to `claude_quota.py`): `get_codex_quota(codex_bin,
   timeout, runner)` → `list[QuotaStatus]`.
   - Start `codex app-server` (stdio JSON-RPC, cwd a temp folder like the claude reader), send
     `initialize` (`clientInfo: {name: "orkcraft", version}`), the `initialized` notification, then
     `account/rateLimits/read` with `{"excludeResetCreditDetails": true}`; close stdin, kill on timeout.
   - For each snapshot (`rateLimitsByLimitId`, else `rateLimits`), one `QuotaStatus` per window:
     `provider="codex"`, `group=limitName or limitId` (`""` for the plain `codex` bucket),
     `window` from `windowDurationMins` (300 → `5h`, 10080 → `weekly`, else `<n>m`),
     `remaining_fraction = 1 - usedPercent/100`, `reset_time = fromtimestamp(resetsAt, UTC)`.
   - An error answer "chatgpt authentication required…" becomes one row with the error
     `API key — no plan windows`, not a failure.
   - **Fallback** when `app-server` is missing or fails: the newest `token_count` with
     `rate_limits` in `~/.codex/sessions/**/rollout-*.jsonl` (skip `.zst` unless `zstandard` is
     there), every shape in §2's table; mark the row `as of <file mtime>` since it is only as fresh
     as the last Codex turn.
2. **`orkcraft/sources/limits.py`**: add `("codex", get_codex_quota, {"timeout": timeout})` to the
   loop, but only when `codex` is on PATH (`sessions.codex_bin()`), so a machine without Codex does
   not get an error row; fix the module docstring.
3. Every place that loops `("claude", "agy")` over limits: `orkcraft/screens/limits_view.py`
   (`mini_status`, the provider colour in `limit_line`), `orkcraft/core/workers/town_hall.py`
   (`lowest`, docstring, `DEMO_LIMITS` gets a codex sample), `orkcraft/realm/metrics.py` docstring.
   Better: one tuple `PROVIDERS = ("claude", "agy", "codex")` in `sources/limits.py` that they import.
   `core/treasury.quota` and the GUI (`gui/views/town_hall.py`, `gui/views/crag.py`) already take
   any provider.
4. **`orkcraft/tools.py` `_codex_login`**: tell the billing by `codex login status` (§3); only
   `CODEX_API_KEY` counts as an API key from the environment. Update `tests/test_tools.py`.
5. Tests: `tests/test_quota_codex.py` with a fake runner answering recorded JSON-RPC lines, and
   rollout fixtures for each `rate_limits` shape.

### 5.2 🪙 Pricing Codex runs

1. **`orkcraft/sources/pricing.py`**: a second table `OPENAI_PRICES: dict[str, OpenAIPrice]`
   (`input`, `cached_input`, `cache_write`, `output`, `long_input/long_cached/long_output`,
   `long_from_tokens`), its own `OPENAI_PRICES_SOURCE` / `OPENAI_PRICES_AS_OF`, and
   `codex_usage_cost(model, usage)`:
   `(input − cached) × in + cached × cached_in + cache_write × write + output × out`, per 1M.
   Codex's `input_tokens` **include** the cached ones ✓ (`TokenUsage::non_cached_input` in
   `C/codex-rs/protocol/src/protocol.rs` ~2430); reasoning tokens are part of `output_tokens` (?:
   OpenAI API convention, not re-checked here). Unknown model → `None`, never $0. Fill the table
   only from the OpenAI page read by a person (§4).
2. **`orkcraft/realm/roads.py` `codex_result_of`** returns a cost: it needs the model, which
   `exec --json` does not print — use the `--model` orkcraft passed (`codex_cmd`), else
   `model` in `$CODEX_HOME/config.toml`, else leave it unpriced. Note: `turn.completed.usage` is the
   **thread's running total** (`usage_from_last_total` ✓ `C/codex-rs/exec/src/event_processor_with_jsonl_output.rs`
   ~118), so summing it over turns double-counts, and after `exec resume` it includes the earlier
   runs' tokens. Take the last `turn.completed` and, for a resume, subtract the total the thread had
   before (or price from the rollout instead, point 3).
3. **War Tent terminals** (`orkcraft/sources/telemetry.py` `_this_run`): Codex's SessionStart hook
   sends `transcript_path` ✓ (`C/codex-rs/hooks/src/events/session_start.rs`), which
   `hooks/session.py` already records. Add a Codex meter that reads that rollout incrementally like
   `_Meter`: model from the latest `turn_context.payload.model`, cost from each `token_count`
   `payload.info.last_token_usage` (per-request, not the total), only lines after the run started.
   Then `harness == "codex"` stops landing in `unpriced`.
4. When the billing is `subscription`, the 🪙 figure is an API-equivalent estimate, as for Claude;
   `core/treasury.quota` already shows the quota instead of 🪙 for subscription tools, so the
   Codex row from 5.1 is what the HUD shows.
5. Docs: `docs/reference.md` (the Limits paragraph, "agy and Codex sessions … unpriced", the
   tools section that says Codex's login is told by `auth.json`), and close the roadmap item.

## 6. Risks

- `account/rateLimits/read` is app-server protocol v2; Codex changes it often (fields were added
  across 0.53 → 0.160). Parse leniently, ignore unknown fields, and keep the rollout fallback.
- `codex app-server` may print notifications (`account/updated`, `account/rateLimits/updated`)
  before the answer; match the response by `id`.
- The prices in §4 are unverified; shipping them unchecked would put wrong dollars in the HUD.
  Until they are checked, ship 5.1 and the token half of 5.2 and leave Codex runs unpriced (`+`).
