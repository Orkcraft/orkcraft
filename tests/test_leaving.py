"""Leaving the camp (docs/design/audience.md §2a, backlog W3): "I'm off" says which carts the orks work on until evening
and the cap, takes the chosen one first, measures the window spent, pauses the Agent pools at the cap and lets them
go on when the person is back; the computer is kept awake only while carts are in work and it is on power."""
from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path
from types import SimpleNamespace

from orkcraft import settings
from orkcraft.core import leaving
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.gui import awake
from orkcraft.gui.away import Away
from orkcraft.realm import event_log
from orkcraft.schedule import Span
from tests.pool_fakes import Steward
from tests.test_gui_pool_clan import _host, _raised

MORNING = dt.datetime(2026, 10, 14, 9, 0)


class _Task(SimpleNamespace):
    pass


class _State:
    def __init__(self, queue=(), tasks=()) -> None:
        self.queue, self.tasks, self.paused, self.saved = list(queue), list(tasks), False, 0

    def save(self) -> None:
        self.saved += 1


class _Pool:
    TYPE = "barracks"

    def __init__(self, state: _State) -> None:
        self.state, self.changes = state, 0

    def changed(self) -> None:
        self.changes += 1

    def pause(self) -> bool:
        self.state.paused = not self.state.paused
        return self.state.paused


class _Town:
    def __init__(self, root: Path | None, pool: _Pool, used: float | None = 10.0) -> None:
        self.repo_root, self.demo, self.published = root, root is None, []
        self.machine = settings.MachineSettings()
        self.machine.tools["claude"].enabled = True              # on a subscription: its window is the cap's
        self.hall = SimpleNamespace(limits=[])
        self.workers = {"pool": pool, "town_hall": self.hall}
        self.used(used)

    def used(self, pct: float | None) -> None:
        self.hall.limits = [] if pct is None else [SimpleNamespace(provider="claude", remaining=1 - pct / 100)]

    def publish(self, topic: str, **data) -> None:
        self.published.append((topic, data))


def _town(root: Path | None, used: float | None = 10.0) -> _Town:
    work = _Task(id="t1", title="Fix the login", status="working")
    queued = [_Task(id="t2", title="Add tests", status="queued"), _Task(id="t3", title="Write the docs", status="queued")]
    return _Town(root, _Pool(_State(queue=queued, tasks=[work, _Task(id="t0", title="Old", status="done")])), used)


def test_the_plan_names_the_carts_until_evening_and_the_cap(tmp_path):
    town = _town(tmp_path)
    plan = leaving.Leaving(town).plan(MORNING)
    assert [c["task"] for c in plan["carts"]] == ["t1", "t2", "t3"]                  # the one at work first, done left out
    assert plan["until"] == "19:00" and plan["cap"] == 30 and plan["window"] == 10.0
    assert "Until 19:00 the orks work on 3 carts: “Fix the login”, “Add tests”, “Write the docs”." in plan["line"]
    assert "up to 30 % of the window" in plan["line"] and plan["line"].endswith("What do they take first?")
    assert "A closed lid still sleeps a laptop: leave the lid open." in plan["lid"]
    town.machine.work = Span.parse("10:00", "18:30")                                 # evening is where the day ends
    assert leaving.Leaving(town).plan(MORNING)["until"] == "18:30"
    town.used(None)                                                                  # no window to read: said plainly
    assert "only the spend limit in Town settings holds them" in leaving.Leaving(town).plan(MORNING)["line"]
    empty = _Town(tmp_path, _Pool(_State()))
    assert "No cart is in work" in leaving.Leaving(empty).plan(MORNING)["line"]


def test_im_off_takes_the_chosen_cart_first_and_is_counted_and_kept(tmp_path):
    town = _town(tmp_path)
    s = leaving.Leaving(town)
    snap = s.leave("t3", on_power=True, now=MORNING)
    assert [t.id for t in town.workers["pool"].state.queue] == ["t3", "t2"]
    assert snap["until"] == "19:00" and snap["spent"] == 0 and snap["metered"] and not snap["capped"]
    [left] = [r for r in event_log.read(tmp_path) if r["event"] == event_log.CAMP_LEFT]
    assert (left["carts"], left["first"], left["cap_pct"], left["on_power"]) == (3, "Write the docs", 30, True)
    assert leaving.Leaving(town).away["first"] == "Write the docs"                    # kept over a restart


def test_the_window_spent_is_summed_through_a_reset_and_the_cap_pauses_the_pools(tmp_path):
    town = _town(tmp_path, used=50)
    s = leaving.Leaving(town)
    s.leave(now=MORNING)
    town.used(70)
    assert s.tick(MORNING.replace(hour=10)) == "" and s.away["spent"] == 20
    town.used(5)                                                                     # the five-hour window reset
    assert s.tick(MORNING.replace(hour=14)) == "" and s.away["spent"] == 20
    town.used(15)
    said = s.tick(MORNING.replace(hour=15))
    assert "spent 30 % of the window" in said and s.capped and town.workers["pool"].state.paused
    assert s.snapshot()["capped"] and s.away["paused"] == ["pool"]
    back = s.back(now=MORNING.replace(hour=16))
    assert not town.workers["pool"].state.paused and s.away is None                  # it takes tasks again
    assert back.startswith("Welcome back. Away since 09:00: 30 % of the window spent, the cap reached")
    [row] = [r for r in event_log.read(tmp_path) if r["event"] == event_log.CAMP_BACK]
    assert (row["why"], row["minutes"], row["capped"], row["carts_left"]) == ("person", 420, True, 3)


def test_a_pool_the_person_paused_stays_paused_and_evening_ends_the_day_away(tmp_path):
    town = _town(tmp_path, used=0)
    town.workers["pool"].state.paused = True
    s = leaving.Leaving(town)
    s.leave(now=MORNING)
    town.used(40)
    s.tick(MORNING.replace(hour=12))
    assert s.capped and s.away["paused"] == []
    said = s.tick(MORNING.replace(hour=19))
    assert said.startswith("Evening") and s.away is None and town.workers["pool"].state.paused


def test_in_the_demo_nothing_is_written(tmp_path):
    s = leaving.Leaving(_town(None))
    s.leave(now=MORNING)
    assert s.away is not None and not list(tmp_path.iterdir())


# -- the computer kept awake ----------------------------------------------------------------------------


class _Proc:
    def __init__(self) -> None:
        self.terminated = False

    def wait(self, timeout=None):
        if self.terminated:
            return 0
        raise subprocess.TimeoutExpired("caffeinate", timeout)

    def terminate(self) -> None:
        self.terminated = True


def _away(tmp_path, power=True):
    town = _town(tmp_path)
    made = []
    a = awake.Awake("darwin", lambda argv, **kw: made.append(_Proc()) or made[-1], lambda n: f"/usr/bin/{n}")
    a.running = True
    host = SimpleNamespace(town=town, awake=a, on_change=lambda: None,
                           you=SimpleNamespace(summary=None, on_news=lambda item: None),
                           muster=SimpleNamespace(roster=SimpleNamespace(alerts=[])))
    away = Away(host)
    away.power = lambda: power
    return away, town, a


def test_it_holds_the_computer_only_while_carts_work_on_power_and_under_the_cap(tmp_path):
    away, town, a = _away(tmp_path)
    assert away.keep_awake() == "caffeinate"                                         # carts in work, on power
    pool = town.workers["pool"].state
    pool.tasks, pool.queue = [], []                                                  # the work is done: it lets go
    assert away.keep_awake() == "" and not a.on
    away2, town2, a2 = _away(tmp_path / "b", power=False)
    assert away2.keep_awake() == "" and not a2.on                                    # on battery: never
    away3, town3, a3 = _away(tmp_path / "c")
    town3.machine.keep_awake = False
    assert away3.keep_awake() == ""                                                  # the setting off


def test_the_cap_lets_the_computer_sleep_and_says_so_once(tmp_path):
    away, town, a = _away(tmp_path)
    away.service.leave(now=dt.datetime.now())
    away.tick(0)
    assert a.on
    town.used(45)
    away.tick(100)
    assert not a.on and "spent 30 % of the window" in away.host.you.summary["text"]


def test_the_page_plans_leaves_and_comes_back(fake_repo, monkeypatch):
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False)
    w = host.town.worker(bid)
    w.state.paused = True                                                            # nothing runs: the carts wait
    for title in ("Fix the login", "Add tests"):
        host.command("act", {"id": bid, "act": "task", "args": {"title": title}})
    plan = host.command("away.plan")
    assert [c["title"] for c in plan["carts"]] == ["Fix the login", "Add tests"] and "keep_awake" in plan
    second = plan["carts"][1]["task"]
    host.command("away.leave", {"first": second})
    assert w.state.queue[0].id == second and host.snapshot()["portrait"]["away"]["until"]
    assert host.command("away.back")["said"].startswith("Welcome back")
    assert host.snapshot()["portrait"]["away"] is None and host.you.summary["text"].startswith("Welcome back")


# -- power ----------------------------------------------------------------------------------------------


def test_power_is_read_each_systems_way(tmp_path):
    run = lambda out: (lambda argv, **kw: SimpleNamespace(stdout=out))               # noqa: E731
    assert awake.on_power("darwin", run("Now drawing from 'AC Power'\n")) is True
    assert awake.on_power("darwin", run("Now drawing from 'Battery Power'\n")) is False
    assert awake.on_power("darwin", run("")) is None

    def supply(name, kind, online=None):
        d = tmp_path / name
        d.mkdir()
        (d / "type").write_text(kind + "\n")
        if online is not None:
            (d / "online").write_text(online + "\n")
    assert awake.on_power("linux", supplies=tmp_path) is True                        # no battery: a desktop
    supply("BAT0", "Battery")
    supply("AC", "Mains", "0")
    assert awake.on_power("linux", supplies=tmp_path) is False
    (tmp_path / "AC" / "online").write_text("1\n")
    assert awake.on_power("linux", supplies=tmp_path) is True
    assert awake.on_power("linux", supplies=tmp_path / "none") is None
    assert awake.on_power("freebsd") is None
