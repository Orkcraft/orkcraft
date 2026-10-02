"""Quota of the AI CLIs, read locally (no model turns, no quota spent) — bundled from limits-watch.

    claude_quota.get_claude_quota()   `claude -p /usage --output-format json`
    agy_quota.get_agy_quota()         `agy -p /usage --output-format json`
Both return a list of `models.QuotaStatus` and never need an API key.
"""
