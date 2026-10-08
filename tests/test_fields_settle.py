"""A task settles before it goes, related ones go together (docs/design/settle-and-join.md): on a board that
sends its tasks by itself a new task is held, a related one joins it and both go as one task; Not urgent
waits longer; a related task that comes after its task went is an addition, which a Barracks adds to the
task it still holds in its queue."""
from __future__ import annotations

import time

import pytest

from orkcraft.core import buildings
from orkcraft.gui.host import Host
from orkcraft.gui.views import fields as view
from orkcraft.realm import checkpoint, pipes, settle

CSV = "Make the CSV export"
DESIGN = "New design for the CSV export: the button on the right"


# -- what is related ----------------------------------------------------------------------------------

def test_words_that_start_alike_are_one_word():
    assert settle.closeness(CSV, DESIGN) == settle.CLOSE
    assert settle.closeness("Сделай фичу экспорта в CSV", "Новый дизайн для экспорта в CSV, кнопка справа") == settle.CLOSE
    assert settle.closeness("Сделай фичу X", "Новый дизайн для фичи X") == settle.CLOSE
    assert settle.closeness("Fix the login bug", "Login page design") == settle.NEAR
    assert settle.closeness("Write the release notes", "Fix the flaky test in CI") == ""
    assert settle.closeness("Make it so", "Add some of that") == ""          # common words never count


def test_the_closest_candidate_wins():
    found = settle.best(DESIGN, [("dark", "Dark mode for the settings"), ("csv", CSV)])
    assert found == ("csv", settle.CLOSE)
    assert settle.best("Speed up the queue", [("csv", CSV)]) == ("", "")


def test_one_task_says_what_came_later_wins():
    text = settle.combined("Make the CSV export", ["New design: the button on the right"])
    assert text.startswith("Make the CSV export\n\n---\n")
    assert f"{settle.ADDED}: New design: the button on the right" in text


def test_a_join_pushes_the_time_back_but_not_forever():
    assert settle.goes_at(came=0, now=60, settle=120) == 180
    assert settle.goes_at(came=0, now=300, settle=120) == 360


# -- the board ----------------------------------------------------------------------------------------

@pytest.fixture
def board(fake_repo, isolated_layout_file, monkeypatch):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "fields")
    spec["config"] = {**(spec.get("config") or {}), "path": "BOARD.md", "send_new": True}
    bid = buildings.raise_spec(host.town, spec).id
    w = host.town.worker(bid)
    sent = []
    monkeypatch.setattr(w, "emit", lambda ev, value, title="", trail=(), ref="", route="":
                        sent.append((ev, value, ref)) or True)
    yield w, sent
    host.close()


def _sent(sent):
    return [(value, ref) for ev, value, ref in sent if ev == "tasks.sent"]


def test_a_new_task_waits_and_says_when_it_goes(board):
    w, sent = board
    card = w.add(CSV, "todo")
    assert not _sent(sent) and w.held(card.id)
    shown = next(c for ln in view.detail(w)["lanes"] for c in ln["cards"] if c["id"] == card.id)
    assert shown["goes"] and not shown["later"]
    assert view.card(w)["waiting"] == 1
    assert w.release_due(time.time() + 10) == 0
    assert w.release_due(time.time() + 121) == 1
    assert _sent(sent) == [(CSV, w.ref(card))] and not w.held(card.id)


def test_settle_zero_sends_at_once_as_before(board):
    w, sent = board
    w.save_config({"settle": 0})
    card = w.add(CSV, "todo")
    assert _sent(sent) == [(CSV, w.ref(card))] and not w.held(card.id)


def test_a_related_task_joins_and_both_go_as_one(board):
    w, sent = board
    first = w.add(CSV, "todo")
    second = w.add(DESIGN, "todo")
    assert w.lore.into(second.id) == first.id and not w.held(second.id)
    assert [c.id for c in w.joined_cards(first.id)] == [second.id]
    w.release_due(time.time() + 1000)
    [(text, ref)] = _sent(sent)
    assert ref == w.ref(first) and CSV in text and DESIGN in text and settle.ADDED in text
    assert w.lore.sent(first.id) and w.lore.sent(second.id)


def test_send_now_on_a_joined_card_sends_its_whole_task(board):
    w, sent = board
    first = w.add(CSV, "todo")
    second = w.add(DESIGN, "todo")
    assert view.ACTS["send"](w, {"card": second.id})
    [(text, ref)] = _sent(sent)
    assert ref == w.ref(first) and DESIGN in text


def test_a_near_task_asks_and_the_person_decides(board):
    w, sent = board
    first = w.add("Fix the login bug", "todo")
    near = w.add("Login page design", "todo")
    assert w.lore.hint(near.id) == first.id and w.held(near.id)
    shown = next(c for ln in view.detail(w)["lanes"] for c in ln["cards"] if c["id"] == near.id)
    assert shown["hint"] == {"id": first.id, "title": "Fix the login bug"}
    assert view.ACTS["apart"](w, {"card": near.id}) and not w.lore.hint(near.id)
    assert view.ACTS["join"](w, {"card": near.id, "into": first.id})
    assert w.lore.into(near.id) == first.id


def test_split_off_makes_it_its_own_task_again(board):
    w, sent = board
    first = w.add(CSV, "todo")
    second = w.add(DESIGN, "todo")
    assert view.ACTS["split"](w, {"card": second.id})
    assert not w.lore.into(second.id) and w.held(second.id)
    w.release_due(time.time() + 1000)
    assert sorted(ref for _, ref in _sent(sent)) == sorted([w.ref(first), w.ref(second)])


def test_not_urgent_waits_longer_and_urgent_again_comes_back(board):
    w, sent = board
    card = w.add(CSV, "todo")
    assert view.ACTS["later"](w, {"card": card.id}) is True
    assert w.lore.hold(card.id) > time.time() + 3000
    w.release_due(time.time() + 600)
    assert not _sent(sent)
    assert view.ACTS["later"](w, {"card": card.id}) is False
    assert w.lore.hold(card.id) < time.time() + 200


def test_a_card_that_leaves_to_do_is_not_going_anywhere(board):
    w, sent = board
    card = w.add(CSV, "todo")
    w.flip(card.id)                                           # a note now
    assert not w.held(card.id)
    w.release_due(time.time() + 1000)
    assert not _sent(sent)


def test_a_joined_card_whose_first_is_deleted_is_held_on_its_own(board):
    w, sent = board
    first = w.add(CSV, "todo")
    second = w.add(DESIGN, "todo")
    w.remove(first.id)
    assert not w.lore.into(second.id) and w.held(second.id)


def test_a_related_task_after_its_task_went_is_an_addition(board):
    w, sent = board
    first = w.add(CSV, "todo")
    w.send(first.id)
    second = w.add(DESIGN, "todo")
    assert w.lore.into(second.id) == first.id and not w.held(second.id)
    (_, ref1), (text, ref2) = _sent(sent)
    assert ref1 == ref2 == w.ref(first)
    assert text.startswith("---\n" + settle.ADDED) and CSV not in text.split(":", 1)[0]


def test_the_work_coming_back_moves_every_card_of_the_task(board):
    w, sent = board
    first = w.add(CSV, "todo")
    second = w.add(DESIGN, "todo")
    w.send(first.id)
    ref = w.ref(first)
    w.receive(pipes.Payload(pipes.TEXT, "Grub (claude) ← Make the CSV export", "camp", "pool.assigned", "t", ref=ref), "", "")
    assert {c.column for c in w.cards} == {"in_progress"}
    w.receive(pipes.Payload(pipes.TEXT, "Done: both", "camp", "pool.done", "t", ref=ref), "", "")
    assert w.card(first.id).column == "done" and w.card(second.id).column == "done"


def test_an_edited_first_card_keeps_its_joined_ones(board):
    w, sent = board
    first = w.add(CSV, "todo")
    second = w.add(DESIGN, "todo")
    w.edit(first.id, "Make the CSV export, quick")
    renamed = next(c for c in w.cards if c.title == "Make the CSV export, quick")
    assert w.lore.into(second.id) == renamed.id and w.held(renamed.id)


# -- the Barracks takes an addition --------------------------------------------------------------------

@pytest.fixture
def camp(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    bid = buildings.raise_spec(host.town, buildings.type_spec(host.town, "barracks")).id
    w = host.town.worker(bid)
    w.state.paused = True                                     # nobody takes the work: it waits in the queue
    yield w
    host.close()


def test_an_addition_to_a_queued_task_grows_its_text(camp):
    task = camp.add_task(CSV, CSV, ref="board:make-the-csv-export")
    more = settle.added(DESIGN)
    again = camp.add_task(CSV, more, ref="board:make-the-csv-export")
    assert again is task and len(camp.state.queue) == 1
    assert task.text.endswith(more) and task.text.startswith(CSV)
    camp.add_task(CSV, more, ref="board:make-the-csv-export")              # the same addition once more: kept once
    assert task.text.count(DESIGN) == 1
    assert any(d.action == "amend" for d in camp.state.decisions())


def test_an_addition_to_a_task_an_ork_took_is_a_follow_up(camp):
    task = camp.add_task(CSV, CSV, ref="board:make-the-csv-export")
    task.status, task.orc = "working", "Grub"
    camp.state.queue.remove(task)
    camp.state.tasks.append(task)
    follow = camp.add_task(CSV, settle.added(DESIGN), ref="board:make-the-csv-export")
    assert follow is not task and follow.ref == task.ref and task.text == CSV


def test_another_cart_with_the_same_ref_is_a_task_of_its_own(camp):
    task = camp.add_task("Prep the sync", "the agenda", ref="drum:sync")
    other = camp.add_task("Prep the sync", "the open items", ref="drum:sync")
    assert other is not task and task.text == "the agenda" and len(camp.state.queue) == 2
