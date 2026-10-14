"""tools/gen_sheets.py (design-system-v3.md §8): the prompts carry what the reviews of v3-prompts learned, the right
references go with them, the key never leaves the environment, and only `--pick` writes a cut sheet. No network."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def gs():
    spec = importlib.util.spec_from_file_location("gen_sheets", ROOT / "tools" / "gen_sheets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_prompt_has_the_head_and_the_reviews_lines(gs):
    for name, sh in gs.SHEETS.items():
        p = gs.build_prompt(name)
        assert p.startswith("No shadows. Pixel-art sprite sheet"), name
        assert "#FF00FF" in p and "never isometric" in p, name
        assert "No frames, no boxes, no grid lines" in p, name
        assert "no smoke, no glow" in p, name
        assert "#7cbd40" in p and "#e4b469" in p, name                       # F1's colours
        assert "No yellow, no orange and no red" in p, name
        assert sh["prompt"] in p and "PNG" in p, name


def test_each_kind_gets_its_lines_and_references(gs):
    for name, sh in gs.SHEETS.items():
        refs = gs.refs_for(name)
        p = gs.build_prompt(name)
        assert refs[0] == "f1-town.jpg", name                                   # F1 always, first
        assert all((gs.REFS / r).exists() for r in refs), name
        if sh["kind"] == "building":
            assert "b1-core.jpg" in refs and "front wall parallel to the bottom edge" in p, name
            assert "No ground under the building" in p, name
        if sh["kind"] == "ork":
            assert {"o1-body.jpg", "o2-roles.jpg"} <= set(refs) and "The same orc as the attached sheets" in p, name
        else:
            assert "The same orc" not in p, name
        if sh["kind"] == "track":
            assert "c2-track.jpg" in refs, name
    body = gs.request_body("o3-states")
    parts = body["contents"][0]["parts"]
    assert parts[0]["text"] == gs.build_prompt("o3-states") and len(parts) == 1 + len(gs.refs_for("o3-states"))
    assert body["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]


def test_only_the_signals_sheet_may_ask_for_yellow_and_red(gs, monkeypatch):
    monkeypatch.setitem(gs.SHEETS, "u4-signals", {"kind": "signals", "expect": 6, "aspect": "1:1",
                                                    "prompt": "a yellow ? bubble", "about": ""})
    p = gs.build_prompt("u4-signals")
    assert "appear nowhere" not in p and "No yellow, no orange" not in p and "ONLY on the signal markers" in p


def test_no_key_stops_before_any_call(gs, monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    def no_network(*a, **k):
        raise AssertionError("a call was made")
    monkeypatch.setattr(gs.urllib.request, "urlopen", no_network)
    assert gs.main(["b2-town"]) == 2
    assert "GEMINI_API_KEY is not set" in capsys.readouterr().out


class _Answer:
    def __init__(self, status, body):
        self.status, self._body = status, json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_client_caps_calls_backs_off_and_stops_on_a_daily_quota(gs, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    sent, slept = [], []
    def opener(req, timeout):
        sent.append(req)
        assert "key=" not in req.full_url and req.get_header("X-goog-api-key") == "test-key-not-real"
        assert req.full_url.startswith("https://generativelanguage.googleapis.com/")
        if len(sent) == 1:
            raise gs.urllib.error.HTTPError(req.full_url, 429, "", {}, _Body({"error": {
                "message": "slow down", "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo",
                                                     "retryDelay": "7s"}]}}))
        return _Answer(200, {"candidates": [{"content": {"parts": [
            {"inlineData": {"mimeType": "image/jpeg", "data": "aGk="}}]}}]})
    c = gs.Client("m", max_calls=2, interval=0, opener=opener, sleep=slept.append)
    data, mime, _ = c.generate({"x": 1})
    assert data == b"hi" and mime == "image/jpeg" and slept == [8.0] and c.calls == 2
    with pytest.raises(gs.Stop, match="cap of 2 calls"):
        c.generate({"x": 1})

    def daily(req, timeout):
        raise gs.urllib.error.HTTPError(req.full_url, 429, "", {}, _Body({"error": {
            "message": "Quota exceeded", "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                                      "violations": [{"quotaId": "GenerateRequestsPerDayPerProject"}]}]}}))
    with pytest.raises(gs.Stop, match="daily quota"):
        gs.Client("m", 5, 0, opener=daily, sleep=slept.append).generate({})


class _Body:
    def __init__(self, body):
        self._b = json.dumps(body).encode()

    def read(self, *a):
        return self._b

    def close(self):
        pass


def test_generated_images_never_land_on_a_cut_name_and_pick_is_the_only_way(gs, tmp_path, monkeypatch):
    refs = tmp_path / "v3"
    monkeypatch.setattr(gs, "REFS", refs)
    monkeypatch.setattr(gs, "CANDIDATES", refs / "candidates")
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    folder = refs / "candidates" / "b2-town"
    dest = gs.save_image(b"\x89PNG fake", "image/png", folder, 1)
    assert dest == folder / "1.png" and not (refs / "b2-town.png").exists()
    with pytest.raises(AssertionError):
        gs.save_image(b"x", "image/png", refs, 1)                      # outside candidates/: refused
    ran = []
    with pytest.raises(gs.Stop, match="no candidate 2"):
        gs.pick("b2-town", 2, run=lambda *a, **k: ran.append(a))
    with pytest.raises(gs.Stop, match="unknown sheet"):
        gs.pick("nope", 1, run=lambda *a, **k: ran.append(a))
    assert not ran and not (refs / "b2-town.png").exists()
    out = gs.pick("b2-town", 1, run=lambda *a, **k: ran.append(a))
    assert out == refs / "b2-town.png" and out.read_bytes() == b"\x89PNG fake"
    assert ran and ran[0][0][-1] == "--v3"                               # then the cutter runs


def test_a_dropped_connection_is_retried(gs, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    tries = []
    def opener(req, timeout):
        tries.append(1)
        if len(tries) == 1:
            raise ConnectionResetError(104, "Connection reset by peer")
        return _Answer(200, {"candidates": [{"content": {"parts": [
            {"inlineData": {"mimeType": "image/png", "data": "aGk="}}]}}]})
    assert gs.Client("m", 3, 0, opener=opener, sleep=lambda s: None).generate({})[1] == "image/png"


def test_a_redrawn_sheet_is_picked_onto_the_sheet_it_redraws(gs):
    assert gs.cut_name("b1-taskboard-s") == "b1-taskboard.png"          # --pick replaces the Task board
    assert gs.cut_name("b2-town") == "b2-town.png"
    assert "b1-taskboard.jpg" in gs.refs_for("b1-taskboard-s") and "g3-palisade.jpg" in gs.refs_for("g3-sides")
