"""🏕 Barracks → 📦 Loot: an ork drafts a post for a service, and posts it only after the operator approves."""
from __future__ import annotations



from orkcraft.realm import barracks as bk
from orkcraft.realm import pipes

SIZE = (200, 46)
CAMP = {"id": "camp", "title": "Camp", "icon": "🏕", "orc": {"name": "Foreman"}, "type": "barracks",
        "config": {"max_orcs": 1, "providers": ["claude"]}}
GATE = {"id": "gate", "title": "Gate", "icon": "📦", "orc": {"name": "Quartermaster"}, "type": "loot",
        "config": {"review": "never"}}                     # even a gate that waves everything through holds a draft


class Writer:
    """Drafts a Jira bug (round n), or — once approved — 'posts' what it was given."""

    def __init__(self):
        self.prompts = []

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        self.prompts.append(prompt)
        if "## Approved" in prompt:
            return "Posted: APP-42 https://jira.example/browse/APP-42", 0.01, 10, "s1"
        n = len(self.prompts)
        return (f"Wrote the bug report (round {n}).\n\nPUBLISH: Jira, project APP, a new Bug\n\n"
                f"Title: Login fails on Safari\nSteps: open the page (v{n})"), 0.02, 20, "s1"


async def _until(pilot, cond, n=150):
    for _ in range(n):
        if cond():
            return True
        await pilot.pause(0.02)
    return cond()


def test_publish_of_splits_the_draft():
    report, target, draft = bk.publish_of("Did it.\n\n**PUBLISH:** Jira, APP\n\nTitle: X\nBody")
    assert (report, target, draft) == ("Did it.", "Jira, APP", "Title: X\nBody")
    assert bk.publish_of("no draft here") == ("no draft here", "", "")
