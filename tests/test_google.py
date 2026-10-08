"""A personal Google account (realm/google.py, docs/design/google-account.md): the client, the sign-in that comes
back to this machine, the tokens kept as logins, and what uses them — Gmail in External listeners, the calendar in
the Calendar, Drive in the Wiki — with Google itself faked."""
from __future__ import annotations

import base64
import datetime as dt
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from orkcraft.realm import feeds, google, logins, watch
from orkcraft.sources import ics, lore

CID = "123456789-abcdefgh123.apps.googleusercontent.com"
SECRET = "GOCSPX-abcdefghijklmn"
ME = "ann@gmail.com"


def _id_token(email: str) -> str:
    part = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{part}.sig"


class _Answer:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


class Google:
    """A fake of Google's endpoints: `routes` maps a URL's start to a JSON answer (or a callable, or an error)."""

    def __init__(self, scope: str = " ".join(google.SCOPES.values()), email: str = ME) -> None:
        self.calls: list[tuple[str, str, bytes | None]] = []
        self.routes: dict[str, object] = {
            google.TOKEN: lambda req: {"access_token": "at-1", "expires_in": 3600, "refresh_token": "rt-1",
                                       "scope": f"openid email {scope}", "id_token": _id_token(email)},
            google.REVOKE: {},
        }

    def __call__(self, req, timeout=None):
        url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
        self.calls.append((req.get_method(), url, req.data))
        for start in sorted(self.routes, key=len, reverse=True):
            if url.startswith(start):
                answer = self.routes[start]
                if callable(answer):
                    answer = answer(req)
                if isinstance(answer, tuple):                  # (status, body): an HTTP error
                    code, body = answer
                    raise urllib.error.HTTPError(url, code, "error", {}, io.BytesIO(json.dumps(body).encode()))
                return _Answer(answer if isinstance(answer, bytes) else json.dumps(answer).encode())
        raise AssertionError(f"unexpected call {url}")


@pytest.fixture(autouse=True)
def _fresh_tokens():
    google._tokens.clear()
    yield
    google._tokens.clear()


def _signed_in(fake: Google, parts=google.PARTS) -> str:
    google.save_client(CID, SECRET)
    c = google.Consent(parts, opener=fake)
    title, _ = c.answer("code-1", "")
    assert title == "Connected", c.error
    return c.account["ref"]


# -- the client ---------------------------------------------------------------------------------------------

def test_the_client_is_pasted_as_id_and_secret_or_as_googles_json_file():
    assert google.parse_client(CID, SECRET) == (CID, SECRET)
    pasted = json.dumps({"installed": {"client_id": CID, "client_secret": SECRET, "redirect_uris": ["http://localhost"]}})
    assert google.parse_client(pasted) == (CID, SECRET)
    with pytest.raises(google.GoogleError, match="Desktop app"):
        google.parse_client(json.dumps({"web": {"client_id": CID, "client_secret": SECRET}}))
    with pytest.raises(google.GoogleError, match="apps.googleusercontent.com"):
        google.parse_client("my-client", SECRET)
    with pytest.raises(google.GoogleError, match="secret"):
        google.parse_client(CID, "")


def test_the_client_is_a_login_on_this_machine_never_in_the_project(tmp_path):
    ref = google.save_client(CID, SECRET)
    assert ref == "keychain:google-client"
    assert google.client() == {"id": CID, "secret": SECRET}
    assert logins.listed("google-client")[0]["account"] == "123456789"
    assert google.forget_client() and google.client() == {}


# -- signing in ---------------------------------------------------------------------------------------------

def test_signing_in_asks_for_the_three_parts_with_pkce_and_comes_back_to_this_machine():
    google.save_client(CID, SECRET)
    c = google.Consent(("gmail", "calendar", "drive"), opener=Google())
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c.url).query)
    assert q["client_id"] == [CID] and q["redirect_uri"][0].startswith("http://127.0.0.1:")
    assert q["code_challenge_method"] == ["S256"] and q["access_type"] == ["offline"]
    assert set(q["scope"][0].split()) == {"openid", "email", *google.SCOPES.values()}
    c.cancel()


def test_googles_answer_through_the_browser_is_kept_as_the_accounts_login():
    fake = Google()
    google.save_client(CID, SECRET)
    c = google.Consent(opener=fake, wait_s=10).start()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c.url).query)
    wrong = f"{c.redirect}/?state=nope&code=x"
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(wrong, timeout=5)              # another sign-in's page: refused, still waiting
    assert c.state == "waiting"
    page = urllib.request.urlopen(f"{c.redirect}/?state={q['state'][0]}&code=code-1", timeout=5).read().decode()
    assert "Connected" in page and c.state == "done"
    sent = urllib.parse.parse_qs(fake.calls[-1][2].decode())
    assert sent["grant_type"] == ["authorization_code"] and sent["code_verifier"][0]
    assert c.account == {"email": ME, "parts": list(google.PARTS), "ref": f"keychain:google-{ME}", "missing": []}
    kept = google.accounts()
    assert [(a["email"], a["parts"]) for a in kept] == [(ME, list(google.PARTS))]
    assert "rt-1" not in json.dumps(kept)                     # the token never leaves realm/google.py


def test_a_refused_sign_in_says_what_happened_and_the_way_round_it():
    google.save_client(CID, SECRET)
    c = google.Consent(opener=Google())
    title, text = c.answer("", "access_denied")
    assert title == "Not connected" and c.state == "failed"
    assert "Advanced" in c.error and "app password" in c.error and "iCal" in c.error
    assert google.accounts() == []


def test_a_part_left_unticked_on_googles_page_is_left_out_and_said():
    google.save_client(CID, SECRET)
    c = google.Consent(opener=Google(scope=google.SCOPES["gmail"]))
    c.answer("code-1", "")
    assert c.account["parts"] == ["gmail"] and c.account["missing"] == ["calendar", "drive"]


def test_none_of_the_parts_allowed_connects_nothing():
    google.save_client(CID, SECRET)
    c = google.Consent(opener=Google(scope=""))
    c.answer("code-1", "")
    assert c.state == "failed" and "none of Gmail, Calendar or Drive" in c.error
    assert google.accounts() == []


def test_no_client_no_sign_in():
    with pytest.raises(google.GoogleError, match="client"):
        google.Consent()


# -- the tokens -----------------------------------------------------------------------------------------------

def test_an_access_token_comes_from_the_refresh_token_once_an_hour():
    fake = Google()
    ref = _signed_in(fake)
    google._tokens.clear()
    assert google.access_token(ref, fake) == "at-1"
    assert google.access_token(ref, fake) == "at-1"
    refreshes = [c for c in fake.calls if c[1] == google.TOKEN and b"refresh_token" in (c[2] or b"")]
    assert len(refreshes) == 1


def test_a_revoked_sign_in_says_connect_again():
    fake = Google()
    ref = _signed_in(fake)
    google._tokens.clear()
    fake.routes[google.TOKEN] = (400, {"error": "invalid_grant"})
    with pytest.raises(google.GoogleError) as e:
        google.access_token(ref, fake)
    assert e.value.kind == "login" and "Connect Google again" in str(e.value)


def test_an_api_turned_off_in_the_project_says_which_and_links_it():
    fake = Google()
    ref = _signed_in(fake)
    fake.routes[f"{google.API}/gmail"] = (403, {"error": {"message": "Gmail API has not been used in project 1 before",
                                                         "errors": [{"reason": "accessNotConfigured"}]}})
    with pytest.raises(google.GoogleError) as e:
        google.gmail_messages(ref, opener=fake)
    assert e.value.kind == "target" and "Gmail API is off" in str(e.value) and "gmail.googleapis.com" in str(e.value)


def test_disconnect_revokes_at_google_and_forgets_here():
    fake = Google()
    _signed_in(fake)
    assert google.disconnect(ME, fake)
    assert any(c[1] == google.REVOKE for c in fake.calls)
    assert google.accounts() == [] and not google.disconnect(ME, fake)


# -- Gmail: External listeners ----------------------------------------------------------------------------

def _mailbox(fake: Google) -> None:
    base = f"{google.API}/gmail/v1/users/me"
    fake.routes[f"{base}/profile"] = {"emailAddress": ME}
    fake.routes[f"{base}/messages?"] = {"messages": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}]}

    def one(mid, frm, to, labels, ms):
        return {"id": mid, "threadId": f"t{mid}", "snippet": "Can we meet  on Friday?", "labelIds": labels,
                "internalDate": str(ms), "payload": {"headers": [{"name": "From", "value": frm},
                                                                 {"name": "To", "value": to},
                                                                 {"name": "Subject", "value": f"About {mid}"}]}}
    fake.routes[f"{base}/messages/m1"] = one("m1", "Bob <bob@x.com>", ME, ["INBOX"], 1_700_000_000_000)
    fake.routes[f"{base}/messages/m2"] = one("m2", "List <list@x.com>", "team@x.com", ["INBOX"], 1_700_000_100_000)
    fake.routes[f"{base}/messages/m3"] = one("m3", f"Ann <{ME}>", "bob@x.com", ["SENT"], 1_700_000_200_000)


def test_a_gmail_line_names_a_sign_in_never_a_password():
    feed, err = feeds.parse(f"gmail: login=keychain:google-{ME} query=in:inbox is:unread")
    assert not err and feed.opts["query"] == "in:inbox is:unread"
    assert feeds.parse("gmail: login=GMAIL_TOKEN")[1].startswith("gmail: login= names a Google sign-in")
    other, _ = feeds.parse("gmail: login=keychain:google-bob@gmail.com")
    assert feed.identity != other.identity                 # two accounts never share what they have seen


def test_new_mail_through_google_is_mail_addressed_to_you_is_a_mention():
    fake = Google()
    ref = _signed_in(fake)
    _mailbox(fake)
    feed, _ = feeds.parse(f"gmail: login={ref}")
    look = feeds.look(feed, fake)
    assert not look.error
    assert [(i.key, i.mention) for i in look.items] == [("m1", True), ("m2", False)]   # your own mail is skipped
    assert look.items[0].title == "@ Bob: About m1"
    assert look.items[0].url == "https://mail.google.com/mail/#all/tm1"
    sig = watch.Signal(watch.now_iso(), "gmail", look.items[0].title, "", "", True)
    assert sig.event == "mail.received"                   # ready towns route mail as mail


def test_a_gmail_look_that_fails_says_which_failure():
    fake = Google()
    ref = _signed_in(fake)
    fake.routes[f"{google.API}/gmail"] = (401, {"error": {"message": "bad"}})
    feed, _ = feeds.parse(f"gmail: login={ref}")
    look = feeds.look(feed, fake)
    assert look.kind == "login" and "connect Google again" in look.error


# -- the calendar: the War Drum -----------------------------------------------------------------------------

def _calendar(fake: Google) -> None:
    fake.routes[f"{google.API}/calendar/v3/calendars/primary/events?"] = {"items": [
        {"id": "e1", "summary": "Standup", "start": {"dateTime": "2026-10-08T09:30:00+00:00"},
         "end": {"dateTime": "2026-10-08T09:45:00+00:00"}},
        {"id": "e2", "summary": "Holiday", "start": {"date": "2026-10-09"}, "end": {"date": "2026-10-10"}},
        {"id": "e3", "summary": "Gone", "status": "cancelled", "start": {"date": "2026-10-09"}}]}


def test_the_week_comes_from_google_calendar_and_is_kept_for_a_while(monkeypatch):
    fake = Google()
    ref = _signed_in(fake)
    _calendar(fake)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    src = ics.CalendarSource("Google Calendar", google=ref)
    day = dt.date(2026, 10, 8)
    events, err = ics.load_events(day, day + dt.timedelta(days=6), [src])
    assert err == []
    assert [e.summary for e in events] == ["Standup", "Holiday"]
    standup = events[0]
    assert standup.start == dt.datetime(2026, 10, 8, 9, 30, tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)
    assert events[1].all_day
    asked = sum("/calendar/" in c[1] for c in fake.calls)
    ics.load_events(day, day + dt.timedelta(days=6), [src])
    assert sum("/calendar/" in c[1] for c in fake.calls) == asked          # from the cache
    fake.routes[f"{google.API}/calendar/v3/calendars/primary/events?"] = (503, {"error": {"message": "down"}})
    ics.forget_google(ref)
    events, err = ics.load_events(day, day + dt.timedelta(days=6), [src])
    assert events == [] and "Google Calendar" in err[0]


def test_new_event_goes_into_the_google_calendar(fake_repo, monkeypatch):
    from orkcraft.core import buildings
    from orkcraft.gui.host import Host
    from orkcraft.realm import checkpoint
    fake = Google()
    ref = _signed_in(fake)
    _calendar(fake)
    fake.routes[f"{google.API}/calendar/v3/calendars/primary/events"] = lambda req: {"id": "new"}
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "war_drum")
    spec["config"] = {**(spec.get("config") or {}), "google": ref}
    built = buildings.raise_spec(host.town, spec)
    w = host.town.worker(built.id)
    w.add("Pricing review", dt.datetime(2026, 10, 9, 14, 0), 45)
    method, url, data = next(c for c in fake.calls if c[0] == "POST" and "/events" in c[1])
    body = json.loads(data)
    assert body["summary"] == "Pricing review"
    start, end = dt.datetime.fromisoformat(body["start"]["dateTime"]), dt.datetime.fromisoformat(body["end"]["dateTime"])
    assert end - start == dt.timedelta(minutes=45) and start.tzinfo is not None
    assert w.writes_to == "Google Calendar" and not w.own_ics.exists()


# -- Drive: the Wiki --------------------------------------------------------------------------------------------

def test_the_wiki_reads_docs_as_markdown_and_text_files_and_skips_the_rest(monkeypatch, tmp_path):
    fake = Google()
    ref = _signed_in(fake)
    fake.routes[f"{google.API}/drive/v3/files?"] = {"files": [
        {"id": "d1", "name": "Pricing", "mimeType": google.DOC, "modifiedTime": "v1", "webViewLink": "https://docs/d1"},
        {"id": "t1", "name": "notes.md", "mimeType": "text/markdown", "modifiedTime": "v1", "size": "20"},
        {"id": "p1", "name": "deck.pdf", "mimeType": "application/pdf", "modifiedTime": "v1"},
        {"id": "b1", "name": "huge.txt", "mimeType": "text/plain", "modifiedTime": "v1", "size": str(google.MAX_BYTES + 1)}]}
    fake.routes[f"{google.API}/drive/v3/files/d1/export?mimeType=text%2Fmarkdown"] = b"# Pricing\n\nThree tiers."
    fake.routes[f"{google.API}/drive/v3/files/t1?alt=media"] = b"- a note"
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    src = lore.parse(f"gdrive:google-{ME}", tmp_path)
    assert isinstance(src, lore.GoogleDriveSource) and src.ref == ref and src.label == f"Google Drive · {ME}"
    src.refresh()
    assert src.error == ""
    base = src.scan()
    assert [n.path for n in base.notes] == ["gdrive:d1", "gdrive:t1"]
    assert src.read("gdrive:d1").startswith("# Pricing\n\nThree tiers.") and "https://docs/d1" in src.read("gdrive:d1")
    exports = sum("/export" in c[1] for c in fake.calls)
    src.refresh()                                       # the same version: not read again
    assert sum("/export" in c[1] for c in fake.calls) == exports


def test_one_folder_of_drive_and_the_folders_in_it(monkeypatch, tmp_path):
    fake = Google()
    _signed_in(fake)
    q = lambda req: urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)["q"][0]   # noqa: E731

    def listing(req):
        if "'F1' in parents" in q(req):
            return {"files": [{"id": "F2", "name": "Sub", "mimeType": google.FOLDER},
                              {"id": "a", "name": "a.txt", "mimeType": "text/plain", "modifiedTime": "1", "size": "3"}]}
        if "'F2' in parents" in q(req):
            return {"files": [{"id": "b", "name": "b.md", "mimeType": "text/markdown", "modifiedTime": "1", "size": "3"}]}
        raise AssertionError(q(req))
    fake.routes[f"{google.API}/drive/v3/files?"] = listing
    fake.routes[f"{google.API}/drive/v3/files/a?alt=media"] = b"aaa"
    fake.routes[f"{google.API}/drive/v3/files/b?alt=media"] = b"bbb"
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    src = lore.parse(f"gdrive:google-{ME}/F1", tmp_path)
    src.refresh()
    assert sorted(n.path for n in src.scan().notes) == ["gdrive:a", "gdrive:b"]


def test_drive_without_a_sign_in_says_so(tmp_path):
    src = lore.parse("gdrive:google-nobody@gmail.com", tmp_path)
    src.refresh()
    assert "connect Google again" in src.error


# -- Settings → Accounts in the GUI (gui/accounts.py) ---------------------------------------------------------

def _host(repo, monkeypatch, fake):
    from orkcraft.gui.host import Host
    from orkcraft.realm import checkpoint
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def test_the_account_goes_into_the_town_raising_what_is_missing(fake_repo, monkeypatch):
    fake = Google()
    _signed_in(fake)
    _mailbox(fake)
    _calendar(fake)
    fake.routes[f"{google.API}/drive/v3/files?"] = {"files": []}
    host = _host(fake_repo, monkeypatch, fake)
    shown = host.command("accounts.list")
    assert shown["client"] == {"id": CID} and shown["accounts"][0]["uses"] == []
    shown = host.command("google.use", {"email": ME})
    uses = {u["part"]: u for u in shown["accounts"][0]["uses"]}
    assert set(uses) == {"gmail", "calendar", "drive"}
    tower, drum, wiki = (host.town.spec_of(uses[p]["id"])["config"] for p in ("gmail", "calendar", "drive"))
    assert f"gmail: login=keychain:google-{ME}" in tower["feeds"]
    assert drum["google"] == f"keychain:google-{ME}"
    assert wiki["sources"][-1] == f"gdrive:google-{ME}" and len(wiki["sources"]) > 1    # its own folders stay
    again = host.command("google.use", {"email": ME})                                   # twice: once in each
    assert host.town.spec_of(uses["gmail"]["id"])["config"]["feeds"].count(f"gmail: login=keychain:google-{ME}") == 1
    assert len(again["accounts"][0]["uses"]) == 3
    host.command("google.folder", {"email": ME, "folder": "F1"})
    assert host.town.spec_of(uses["drive"]["id"])["config"]["sources"][-1] == f"gdrive:google-{ME}/F1"
    host.command("google.disconnect", {"email": ME, "detach": True})
    assert google.accounts() == []
    assert not any("gmail:" in x for x in host.town.spec_of(uses["gmail"]["id"])["config"].get("feeds") or [])
    assert "google" not in host.town.spec_of(uses["calendar"]["id"])["config"]


def test_an_account_not_signed_in_cannot_be_used(fake_repo, monkeypatch):
    from orkcraft.gui.host import CommandError
    host = _host(fake_repo, monkeypatch, Google())
    with pytest.raises(CommandError, match="not connected"):
        host.command("google.use", {"email": ME})
    with pytest.raises(CommandError, match="apps.googleusercontent.com"):
        host.command("google.client", {"id": "nope", "secret": SECRET})
    assert host.command("google.client", {"id": CID, "secret": SECRET})["client"] == {"id": CID}


def test_the_wizard_starts_a_sign_in_the_page_polls(fake_repo, monkeypatch):
    fake = Google()
    host = _host(fake_repo, monkeypatch, fake)
    host.command("google.client", {"id": CID, "secret": SECRET})
    got = host.command("google.connect", {"parts": ["calendar"]})
    assert got["consent"]["state"] == "waiting" and "calendar.events" in got["consent"]["url"]
    assert "gmail" not in got["consent"]["url"]
    assert host.command("google.cancel")["consent"] is None
    time.sleep(0.05)
