"""Feature shots for the landing: the mechanisms behind the three pillars.

Each shot drives the real pipeline — the Recruiter's checks, Mason & Artisan's validation, the
steward's metrics, findings and replay, the War Horn — with a scripted runner in place of the
model, so no call is made. Where the model's answer comes from a real run it is marked
"recorded": the Recruiter's answer was produced by Claude in T1098 (only its source building was
renamed for this sandbox); the steward's proposal matches the one Claude made in the same ticket's
real run. Mason's and Artisan's answers are examples.
"""
from __future__ import annotations

import json
from pathlib import Path

from orkcraft.realm import roads

# Recorded: Claude's answer to «когда в Forge выбираю задачу в статусе done, покажи одну строку:
# id и заголовок» (T1098 stage 3 real run), the source renamed to this sandbox's Forge.
RECRUITER_ANSWER = {
    "name": "Done Task Line", "role": "Shows one line, the id and title, when a done task is selected in Forge",
    "kind": "chain",
    "why": ("A road filter at the source keeps only selected tasks with status done. One template op then "
            "prints the id and title from the record, so no script or agent is needed."),
    "orders": "", "harness": [], "chain": [{"op": "template", "md": "{id} — {title}"}], "script_source": "",
    "roads": [{"from": "oauth_forge", "event": "on_selection_change",
               "filter": {"node_type": ["task"], "node_status": ["done"], "exclude_personal": True}}],
}

MASON_ANSWER = {
    "id": "ci_watch", "title": "CI Watch", "icon": "🛠", "summary": "failing tests next to the open feature tasks",
    "orc": {"name": "Tinker", "role": "watches the test log"},
    "data": [{"name": "open", "source": "graph_nodes", "params": {"tag": "feat_oauth", "status": "todo", "limit": 20}},
             {"name": "log", "source": "file_tail", "params": {"path": "demo/feat_oauth/pytest.log", "lines": 25}}],
}
ARTISAN_ANSWER = {**MASON_ANSWER,
                  "layout": {"direction": "horizontal", "panes": [
                      {"widget": "table", "data": "open", "title": "Open tasks", "ratio": 2, "columns": ["id", "title", "status"]},
                      {"widget": "log", "data": "log", "title": "pytest", "ratio": 3}]},
                  "actions": [{"key": "O", "label": "Open card", "action": "node:open"}]}

# The steward's case: the Herald Desk agent of Delivery-Control has announced every blocker as
# one line — a template's job. Recorded shape of Claude's proposal in T1098 stage 7.
STEWARD_PROPOSAL = {"proposals": [{
    "type": "demote", "orc": "herald_desk",
    "why": ("All 6 runs produced the same one-line shape '📌 <text>' built purely from the input text. "
            "A template chain reproduces the recorded output exactly; no model is needed."),
    "chain": [{"op": "template", "md": "📌 {text}"}]}]}
BLOCKERS = ["feat/oauth-flow blocked: security review 2 d", "test/e2e-matrix CI red 6 h", "chore/tokens-v2 breaks 4 repos",
            "feat/stripe-billing waiting for prod keys", "release 4.13 in 3 days, 2 blockers", "OPS-77 on-call overload"]


def seed_steward_examples(root: Path) -> None:
    path = roads.examples_file(root, "dc_loot", "herald_desk")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for text in BLOCKERS:
            f.write(json.dumps({"inputs": [{"road": "dc_watch-task", "source": "dc_watch", "event": "on_task_completed",
                                            "kind": "text", "text": text, "value": text, "title": "Overseer · task completed"}],
                                "output": f"📌 {text}"}, ensure_ascii=False) + "\n")


def runner_of(answers: list[dict]):
    """A scripted model: returns the answers in turn, no cost."""
    queue = list(answers)

    def run(prompt: str):
        return json.dumps(queue.pop(0) if len(queue) > 1 else queue[0], ensure_ascii=False), None
    return run
