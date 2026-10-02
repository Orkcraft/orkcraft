"""🛠 From scratch (T1108 stage 5): interview → script-first blueprint → Council + sandbox → approval."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft.realm import blueprint, checkpoint, fastpath, workshop

COUNT = """import json, sys
cart = json.load(sys.stdin)
words = cart["value"].split()
if not words:
    sys.exit(3)
print(json.dumps({"words": len(words), "first": words[0]}))
sys.exit(4 if len(words) > 5 else 0)
"""
BP = {"id": "word_count", "title": "Word Count", "icon": "🔢", "summary": "counts the words of a paste",
      "runtime": "python", "script": COUNT, "steward_prompt": "", "steward_why": "",
      "mocks": [{"event": "pit.text", "source": "pit", "title": "", "value": "one two three"},
                {"event": "pit.text", "source": "pit", "title": "", "value": "a b c d e f g"}]}
INTERVIEW = {"purpose": "count the words of what I paste into the pit", "layout": "card",
             "inputs": ["pit:pit.text"], "events": ["workshop.done", "workshop.failed", "workshop.alert"]}


def test_the_sandbox_runs_the_contract_in_a_bare_folder():
    runs = workshop.sandbox(COUNT, "python", BP["mocks"] + [workshop.cart("pit.text", "pit", "")])
    assert [r.outcome for r in runs] == ["done", "alert", "escalated"]
    assert json.loads(runs[0].out) == {"words": 3, "first": "one"}
    env = workshop.sandbox("import os, json; print(json.dumps(sorted(os.environ)))", "python", [workshop.cart("e", "s", "")])
    assert not [k for k in json.loads(env[0].out) if k.startswith("ORKCRAFT_")]
    bash = workshop.sandbox('read -r line; echo "got ${#line}"; exit 1', "bash", [workshop.cart("e", "s", "x")])
    assert bash[0].outcome == "failed" and bash[0].out.startswith("got")
    assert workshop.check_syntax("def x(:", "python") and workshop.check_syntax("if then fi", "bash")
    assert workshop.check_syntax(COUNT, "python") == ""
    assert workshop.shape('[{"a": 1}]')[0] == "rows" and workshop.shape('{"a": 1}')[0] == "card"
    assert workshop.shape("plain")[0] == "text"


def test_the_sandbox_stops_a_slow_script(monkeypatch):
    monkeypatch.setattr(workshop, "SANDBOX_TIMEOUT_S", 1)
    r = workshop.sandbox("import time; time.sleep(5)", "python", [workshop.cart("e", "s", "")])[0]
    assert r.code == -1 and "no answer" in r.err


def test_the_builder_retries_with_its_problems_and_the_operators_note():
    prompts = []
    answers = iter(["no json here", json.dumps(dict(BP, steward_prompt="summarise it")), json.dumps(BP)])

    def runner(prompt):
        prompts.append(prompt)
        return next(answers), 0.01

    result = blueprint.build(INTERVIEW, {"pit"}, runner, feedback="count lines too")
    assert result.ok and len(result.attempts) == 3 and result.cost_usd == pytest.approx(0.03)
    assert "ONE JSON object" in prompts[1] and "steward_why" in prompts[2] and "count lines too" in prompts[0]
    bp = result.blueprint
    assert bp["layout"] == "card" and bp["inputs"] == ["pit:pit.text"] and len(bp["mocks"]) == 2
    spec = blueprint.to_spec(bp)
    assert spec["type"] == "workshop" and spec["config"] == {"runtime": "python", "layout": "card",
                                                              "inputs": ["pit:pit.text"]}
    assert blueprint.problems(dict(BP, id="pit"), {"pit"}) == ["id: pit is taken — pick another"]
    failed = blueprint.build(INTERVIEW, set(), lambda p: (_ for _ in ()).throw(RuntimeError("no claude")))
    assert not failed.ok and "no claude" in failed.error


def test_the_council_blocks_a_dangerous_script_before_the_sandbox(tmp_path: Path):
    spec = blueprint.to_spec(blueprint.normalise(dict(BP, script="import os\nos.system('sudo rm -rf /')\n"), INTERVIEW))
    v = fastpath.review(fastpath.Subject("building", "word_count", spec, "import os\nos.system('sudo rm -rf /')\n"), tmp_path)
    assert v.blocked and any("sudo" in n.text for n in v.notes)


async def _wait(pilot, cond, n: int = 80) -> bool:
    for _ in range(n):
        await pilot.pause(0.05)
        if cond():
            return True
    return False


READY = {"ready": True, "purpose": "Count the words of every paste; alert on long ones.",
         "views": [{"name": "Counter card", "layout": "card", "preview": "words 12\nfirst release"},
                   {"name": "Run log", "layout": "log", "preview": "✓ 05:01 12 words"},
                   {"name": "Word table", "layout": "table", "preview": "| word | n |"}],
         "inputs": ["pit:pit.text"], "events": ["workshop.done", "workshop.alert"]}


def test_the_builder_asks_then_offers_three_views():
    answers = iter([json.dumps({"questions": ["Which pastes?", "Alert when?"]}),
                    json.dumps(dict(READY, views=READY["views"][:2])),           # two views: rejected
                    json.dumps(READY)])
    prompts = []

    def runner(p):
        prompts.append(p)
        return next(answers), 0.001

    sources = [("pit:pit.text", "The Pit → text pasted")]
    first = blueprint.talk([("builder", "What?"), ("operator", "count words")], sources, runner)
    assert first.questions == ["Which pastes?", "Alert when?"] and not first.ready
    assert "operator: count words" in prompts[0] and "pit:pit.text" in prompts[0]
    second = blueprint.talk([("operator", "all of them; over 400 words")], sources, runner)
    assert second.ready and [v["layout"] for v in second.views] == ["card", "log", "table"]
    assert "exactly three" in prompts[2]
    iv = blueprint.interview_from(second, 2, ["pit:pit.text"], ["workshop.done"], [("operator", "x")])
    assert iv["layout"] == "table" and "Word table" in iv["purpose"] and iv["history"] == [("operator", "x")]
    bad = blueprint.talk([], sources, lambda p: (json.dumps(dict(READY, inputs=["mail:x"])), 0.0))
    assert bad.error and "inputs" in bad.error


@pytest.mark.asyncio
async def test_from_scratch_end_to_end(fake_repo: Path, monkeypatch):
    from textual.widgets import Input, RadioButton, TextArea

    from orkcraft import app as app_mod
    from orkcraft.app import OrkcraftApp
    from orkcraft.realm import pipes
    from orkcraft.screens.builder_interview import BlueprintReview, BuilderChat
    from orkcraft.screens.typed.workshop_view import WorkshopView

    prompts = []

    def builder(prompt):
        prompts.append(prompt)
        if "THE CONVERSATION SO FAR" in prompt:
            return json.dumps(READY), 0.001
        return json.dumps(BP), 0.02

    monkeypatch.setattr(app_mod, "BUILD_RUNNER", builder)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        assert app.build_from_type("pit")
        await pilot.pause()
        app.action_build_scratch()
        await pilot.pause()
        chat = app.screen
        assert isinstance(chat, BuilderChat) and chat.query_one("#chat-draft").disabled
        chat.query_one("#chat-input", Input).value = INTERVIEW["purpose"]
        await pilot.press("enter")
        assert await _wait(pilot, lambda: chat.turn is not None)
        assert not chat.query_one("#chat-draft").disabled and "count the words" in prompts[0]
        chat.query_one("#chat-view-0", RadioButton).value = True                   # the card
        await pilot.press("ctrl+s")
        assert await _wait(pilot, lambda: isinstance(app.screen, BlueprintReview))
        review = app.screen
        assert review.passed and "card" in prompts[1] and "Counter card" in prompts[1] and "pit:pit.text" in prompts[1]

        # reject: back to the conversation; what is said there goes to the next draft
        await pilot.press("ctrl+n")
        assert await _wait(pilot, lambda: isinstance(app.screen, BuilderChat) and app.screen is not chat)
        chat2 = app.screen
        assert chat2.history[-1] == ("builder", "What should I change in the blueprint?")
        chat2.query_one("#chat-input", Input).value = "also say the first word"
        await pilot.press("enter")
        assert await _wait(pilot, lambda: chat2.turn is not None)
        await pilot.press("ctrl+s")
        assert await _wait(pilot, lambda: isinstance(app.screen, BlueprintReview) and app.screen is not review)
        assert "also say the first word" in prompts[-1] and "THE REJECTED SCRIPT" in prompts[-1]
        review = app.screen

        # an edit must be re-run before approval; a broken edit blocks
        area = review.query_one("#bp-script", TextArea)
        area.text = COUNT.replace("sys.exit(4 if len(words) > 5 else 0)", "sys.exit(1)")
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.screen is review and "re-run" in str(review.query_one("#bp-errors").render())
        await pilot.press("ctrl+r")
        assert await _wait(pilot, lambda: not review.checking)
        assert not review.passed and review.query_one("#bp-approve").disabled
        area.text = COUNT
        await pilot.press("ctrl+r")
        assert await _wait(pilot, lambda: not review.checking and review.passed)
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.pause()

        spec = app.custom_specs["word_count"]
        assert spec["type"] == "workshop" and spec["config"]["layout"] == "card"
        assert (fake_repo / ".orkcraft/scripts/word_count/main.py").read_text() == COUNT
        assert workshop.load_blueprint(fake_repo, "word_count")["mocks"]
        assert [r.source for r in app.scroll.building("word_count").roads] == ["pit"]
        tracked = checkpoint._git(fake_repo, "ls-files").stdout.split()
        assert "scripts/word_count/main.py" in tracked and "blueprints/word_count/blueprint.json" in tracked
        assert [r["decision"] for r in fastpath.recent(fake_repo)][:2] == ["approved", "cancelled"]

        view = app._custom_view("word_count")
        assert isinstance(view, WorkshopView)
        sent = []
        monkeypatch.setattr(app, "emit_typed", lambda b, ev, value, title="": sent.append((ev, value)) or True)
        view.receive(pipes.Payload(pipes.TEXT, "red green blue", "pit", "pit.text"), "", "")
        assert await _wait(pilot, lambda: bool(sent))
        assert sent[0][0] == "workshop.done" and json.loads(sent[0][1])["words"] == 3

        # exit 3: the steward prompt takes the cart
        view.spec = dict(view.spec, config=dict(view.spec["config"], steward_prompt="say what it is"))
        WorkshopView.steward_runner = staticmethod(lambda p: ("an empty paste", 0.0))
        try:
            sent.clear()
            view.run_cart(workshop.cart("pit.text", "pit", ""))
            assert await _wait(pilot, lambda: bool(sent))
            assert sent[0] == ("workshop.done", "an empty paste")
        finally:
            WorkshopView.steward_runner = None
        tests = view.run_tests()
        assert [r.outcome for r in tests] == ["done", "alert"]


@pytest.mark.asyncio
async def test_the_build_menu_offers_from_scratch_second(fake_repo: Path):
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.builder_interview import BuilderChat, BuilderInterview

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app.action_build_menu()
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()
        assert isinstance(app.screen, BuilderChat)
        await pilot.click("#chat-form")                                  # the plain form is still there
        await pilot.pause()
        assert isinstance(app.screen, BuilderInterview)
        await pilot.press("ctrl+s")                                     # an empty interview stays open
        await pilot.pause()
        assert isinstance(app.screen, BuilderInterview)
        assert "say in a sentence" in str(app.screen.query_one("#iv-errors").render())


@pytest.mark.asyncio
async def test_the_blueprint_previews_and_emulates(fake_repo: Path, monkeypatch):
    from textual.widgets import Input

    from orkcraft.app import OrkcraftApp
    from orkcraft.screens import builder_interview as bi

    monkeypatch.setattr(bi, "EMULATE_STEP_S", 0.01)
    bp = blueprint.normalise(BP, INTERVIEW)                                  # layout: card
    runs = workshop.sandbox(bp["script"], "python", bp["mocks"])
    verdict = fastpath.review(fastpath.Subject("building", bp["id"], blueprint.to_spec(bp), bp["script"]), fake_repo)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        screen = bi.BlueprintReview(bp, verdict, runs, lambda b: (verdict, runs))
        app.push_screen(screen)
        await pilot.pause()
        preview = str(screen.query_one("#bp-preview").render())
        assert "words" in preview and "first" in preview and "Word Count" in preview      # the card, the hut
        await pilot.press("ctrl+e")
        assert await _wait(pilot, lambda: "■ done" in str(screen.query_one("#bp-emulate").render()))
        log = str(screen.query_one("#bp-emulate").render())
        assert "cart 1 · pit.text from pit" in log and "workshop.alert" in log
        screen.query_one("#bp-try", Input).value = "just two"
        screen.query_one("#bp-try", Input).focus()
        await pilot.press("enter")
        assert await _wait(pilot, lambda: "your cart" in str(screen.query_one("#bp-emulate").render()))
        assert "2" in str(screen.query_one("#bp-preview").render())


@pytest.mark.asyncio
async def test_a_workshop_runs_on_its_own_timer(fake_repo: Path, monkeypatch):
    import datetime as dt

    from orkcraft.app import OrkcraftApp

    bp = blueprint.normalise(dict(BP, schedule="every 15m"), dict(INTERVIEW, schedule="every 15m"))
    spec = blueprint.to_spec(bp)
    assert spec["config"]["schedule"] == "every 15m"
    from orkcraft.realm import masonry
    assert masonry.validate_spec(dict(spec, config=dict(spec["config"], schedule="sometimes")), fake_repo, set())
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        assert app.raise_blueprint(bp)
        await pilot.pause()
        view = app._custom_view("word_count")
        sent = []
        monkeypatch.setattr(app, "emit_typed", lambda b, ev, value, title="": sent.append((ev, value)) or True)
        view.last_tick = dt.datetime(2026, 10, 2, 6, 0)                    # every 15m: :00 :15 :30 :45
        assert not view.tick(dt.datetime(2026, 10, 2, 6, 14))
        assert view.tick(dt.datetime(2026, 10, 2, 6, 16))
        assert await _wait(pilot, lambda: bool(sent))
        assert sent[0][0] == "workshop.done" and view.runs[0].event == "workshop.tick"
