"""Quota of the AI CLIs, read locally (no model turns, no quota spent) — bundled from limits-watch.

    claude_quota.get_claude_quota()   `claude -p /usage --output-format json`
    agy_quota.get_agy_quota()         `agy -p /usage --output-format json`
    codex_quota.get_codex_quota()     `codex app-server` `account/rateLimits/read`, else the session rollouts
All return a list of `models.QuotaStatus` and never need an API key.
"""
