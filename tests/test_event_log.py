"""The local event log (realm/event_log.py, docs/design/dogfood-logs.md §3): exact, local, never sent."""
import datetime as dt
import io
import json
import zipfile

from orkcraft.realm import analytics, event_log


def test_an_event_is_one_exact_line_in_the_towns_folder(tmp_path):
    assert event_log.record(tmp_path, event_log.ASKED, building="pool", ork="Grunt", task="t1", harness="claude",
                            text="Which port?", options=["8080", "3000"], via="block")
    [row] = event_log.read(tmp_path)
    assert (tmp_path / ".orkcraft" / "usage" / "events.jsonl").is_file()
    assert row["event"] == "question_asked" and row["text"] == "Which port?" and row["options"] == ["8080", "3000"]
    assert dt.datetime.fromisoformat(row["at"]).tzinfo is not None


def test_an_unknown_event_or_no_root_writes_nothing(tmp_path):
    assert not event_log.record(tmp_path, "something_else", x=1)
    assert not event_log.record(None, event_log.ASKED, text="demo")
    assert event_log.read(tmp_path) == []


def test_only_plain_data_is_kept_and_long_text_is_cut(tmp_path):
    event_log.record(tmp_path, event_log.ASSUMED, text="x" * 5000, obj=object(), n=3, ok=True)
    [row] = event_log.read(tmp_path)
    assert len(row["text"]) == event_log.TEXT_MAX and "obj" not in row and row["n"] == 3 and row["ok"] is True


def test_counts_and_the_weeks_summary(tmp_path):
    old = dt.datetime(2026, 10, 1, 9, tzinfo=dt.timezone.utc)
    (tmp_path / event_log.PATH).parent.mkdir(parents=True)
    (tmp_path / event_log.PATH).write_text(json.dumps(event_log.line(event_log.ASKED, at=old)) + "\nnot json\n")
    for who, waited in (("person", 600), ("person", 60), ("steward", 5), ("person", 120)):
        event_log.record(tmp_path, event_log.ANSWERED, building="pool", task="t", who=who, waited_s=waited)
    event_log.record(tmp_path, event_log.STOPPED, building="pool", task="t")
    c = event_log.counts(tmp_path, since="2026-10-10")
    assert c["question_answered"] == 4 and c["run_stopped_on_question"] == 1 and c["question_asked"] == 0
    assert event_log.counts(tmp_path)["question_asked"] == 1
    s = event_log.summary(tmp_path, since="2026-10-10")
    assert s["answer_wait_median_s"] == 120 and s["counts"]["quest_done"] == 0


def test_the_analytics_zip_carries_the_periods_events(tmp_path):
    today = dt.date.today().isoformat()
    event_log.record(tmp_path, event_log.QUEST_DONE, quest="1", seconds=40)
    z = zipfile.ZipFile(io.BytesIO(analytics.pack(tmp_path, [today], {}, lambda b, d: [], lambda b, d: [])))
    [row] = [json.loads(x) for x in z.read("events.jsonl").decode().splitlines()]
    assert row["event"] == "quest_done" and row["quest"] == "1"


def test_cli_usage_local_prints_the_counts(fake_repo, capsys):
    from orkcraft.cli import main
    event_log.record(fake_repo, event_log.ASKED, text="?")
    event_log.record(fake_repo, event_log.ANSWERED, who="person", waited_s=300)
    assert main(["--repo", str(fake_repo), "usage", "local"]) == 0
    out = capsys.readouterr().out
    assert "never sent" in out and "question asked: 1" in out and "median wait for your answer: 5 min" in out
