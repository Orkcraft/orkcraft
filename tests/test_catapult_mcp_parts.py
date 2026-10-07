"""🎯 The Catapult through MCP, its parts without a face (realm/catapult_mcp/, docs/design/catapult-mcp.md):
templates learned from a call, direct routes from recipes, the carrier's check, the local client."""
from __future__ import annotations

import io
import json
import smtplib
import subprocess
import sys
import urllib.error
from pathlib import Path

from orkcraft.realm import harnesses, mcp
from orkcraft.realm.catapult_mcp import carrier, local, routes, templates as tp

CART = {"notes": "v0.2: roofs and roads", "version": {"tag": "v0.2"}, "draft": True}


def test_a_recorded_call_becomes_a_template_over_the_cart():
    args = {"channel_id": "C01", "text": "v0.2: roofs and roads", "tag": "v0.2", "unfurl": True}
    t = tp.learn(args, CART)
    assert t == {"channel_id": "C01", "text": {"$": "notes"}, "tag": {"$": "version.tag"}, "unfurl": True}
    assert tp.render(t, {"notes": "v0.3", "version": {"tag": "v0.3"}})["text"] == "v0.3"
    assert tp.learn({"payload": json.dumps(CART)}, CART) == {"payload": {"$": ""}}     # the whole cart
    assert tp.from_lines(['channel = "C01"', "text = notes", "n = 5", "all = ."]) == \
        {"channel": "C01", "text": {"$": "notes"}, "n": 5, "all": {"$": ""}}
    assert "text ← notes" in tp.describe(t)
    try:
        tp.render({"x": {"$": "nope"}}, CART)
        raise AssertionError("a missing path must say so")
    except tp.Missing as e:
        assert "nope" in str(e)


class Opener:
    def __init__(self, answer: bytes = b'{"ok": true}', status: int = 200, error: int = 0) -> None:
        self.answer, self.status, self.error, self.requests = answer, status, error, []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.error:
            raise urllib.error.HTTPError(req.full_url, self.error, "no", {}, io.BytesIO(self.answer))
        return _Resp(self.answer, self.status)


class _Resp:
    def __init__(self, data: bytes, status: int) -> None:
        self.f, self.status = io.BytesIO(data), status

    def __enter__(self):
        return self

    def __exit__(self, *a) -> None:
        pass

    def read(self, *a):
        return self.f.read(*a)


def test_slack_gets_its_api_and_its_webhook_and_slack_s_own_refusals_are_read():
    t = tp.learn({"channel_id": "C01", "text": "v0.2: roofs and roads"}, CART)
    found, cost = routes.derive("slack", "mcp__slack__slack_post_message", t)
    assert cost == 0.0 and [routes.title(r) for r in found] == ["Slack API", "Slack webhook"]
    api, hook = found
    assert api["body"] == {"channel": "C01", "text": {"$": "notes"}} and routes.needs(api) == ["SLACK_BOT_TOKEN"]
    env = {"SLACK_BOT_TOKEN": "xoxb-secret"}
    net = Opener()
    shot, kind = routes.send(api, CART, env, opener=net)
    req = net.requests[0]
    assert shot.ok and kind == "" and req.get_header("Authorization") == "Bearer xoxb-secret"
    assert json.loads(req.data) == {"channel": "C01", "text": "v0.2: roofs and roads"}
    assert "xoxb" not in shot.body + shot.url and "xoxb" not in routes.preview(api, CART, env)
    shot, kind = routes.send(api, CART, env, opener=Opener(b'{"ok": false, "error": "invalid_auth"}'))
    assert not shot.ok and kind == "auth" and shot.error == "invalid_auth"
    shot, kind = routes.send(api, CART, env, opener=Opener(b'{"ok": false, "error": "channel_not_found"}'))
    assert not shot.ok and kind == "path"
    shot, kind = routes.send(api, CART, {}, opener=Opener())
    assert kind == "auth" and "SLACK_BOT_TOKEN" in shot.error            # not set: nothing goes out
    net = Opener(b"ok")
    shot, _ = routes.send(hook, CART, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/T/B/secret"}, opener=net)
    assert shot.ok and net.requests[0].full_url.endswith("/secret") and shot.url == "$SLACK_WEBHOOK_URL"


def test_jira_issues_and_comments_take_the_site_from_the_environment():
    t = {"projectKey": "REL", "summary": {"$": "version.tag"}, "description": {"$": "notes"}}
    (issue,) = routes.derive("atlassian", "mcp__atlassian__createJiraIssue", t)[0]
    env = {"JIRA_URL": "https://acme.atlassian.net/", "JIRA_EMAIL": "me@acme.io", "JIRA_API_TOKEN": "t"}
    net = Opener(b'{"key": "REL-7"}', 201)
    shot, kind = routes.send(issue, CART, env, opener=net)
    body = json.loads(net.requests[0].data)
    assert shot.ok and net.requests[0].full_url == "https://acme.atlassian.net/rest/api/2/issue"
    assert body["fields"] == {"project": {"key": "REL"}, "issuetype": {"name": "Task"}, "summary": "v0.2",
                              "description": "v0.2: roofs and roads"}
    assert net.requests[0].get_header("Authorization").startswith("Basic ")
    (comment,) = routes.derive("jira", "mcp__jira__add_comment", {"issue_key": "REL 7", "body": {"$": "notes"}})[0]
    net = Opener(b"{}", 201)
    routes.send(comment, CART, env, opener=net)
    assert net.requests[0].full_url.endswith("/rest/api/2/issue/REL%207/comment")
    shot, kind = routes.send(comment, CART, env, opener=Opener(b'{"errorMessages": ["no"]}', error=404))
    assert kind == "path" and shot.status == 404
    shot, kind = routes.send(comment, CART, env, opener=Opener(b"", error=401))
    assert kind == "auth"


def test_notion_drops_an_optional_paragraph_and_discord_a_missing_channel():
    (page,) = routes.derive("notion", "mcp__notion__create_page", {"parent_id": "p1", "title": {"$": "version.tag"}})[0]
    body = routes._body(page, CART, {})
    assert body["children"] == [] and body["parent"] == {"page_id": "p1"}
    found, _ = routes.derive("discord", "mcp__discord__send_message", {"content": {"$": "notes"}})
    assert [routes.title(r) for r in found] == ["Discord webhook"]           # no channel: no bot API route


def test_a_model_matches_names_the_recipe_does_not_know_and_sees_no_values():
    seen = []

    def runner(prompt, model=None):
        seen.append(prompt)
        return '{"action": 0, "args": {"channel": "where", "text": "words"}}', 0.01

    found, cost = routes.derive("slack", "mcp__slack__post_message", {"channel": "C01", "text": {"$": "notes"}}, runner)
    assert found and seen == []                                               # the recipe's own names: no model
    assert routes.derive("slack", "mcp__slack__shout", {"where": "C01"})[0] == []   # no model asked: nothing
    found, cost = routes.derive("slack", "mcp__slack__shout", {"where": "C01", "words": {"$": "notes"}}, runner)
    assert routes.title(found[0]) == "Slack API" and found[0]["body"]["channel"] == "C01" and cost == 0.01
    assert "C01" not in seen[0] and "words" in seen[0]


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port) -> None:
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a) -> None:
        pass

    def starttls(self) -> None:
        pass

    def login(self, user, password) -> None:
        if password != "app-pass":
            raise smtplib.SMTPAuthenticationError(535, b"no")

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)
        return {}


def test_an_email_goes_by_smtp_with_an_app_password():
    t = {"to": "team@acme.io", "subject": {"$": "version.tag"}, "body": {"$": "notes"}}
    smtp, resend = routes.derive("claude_ai_Gmail", "mcp__claude_ai_Gmail__send_email", t)[0]
    assert routes.title(smtp) == "SMTP" and routes.title(resend) == "Resend API"
    env = {"SMTP_HOST": "smtp.acme.io", "SMTP_USER": "me", "SMTP_PASSWORD": "app-pass", "SMTP_FROM": "me@acme.io"}
    shot, kind = routes.send(smtp, CART, env, smtp=FakeSMTP)
    msg = FakeSMTP.sent[-1]
    assert shot.ok and msg["To"] == "team@acme.io" and msg["Subject"] == "v0.2" and "roofs" in msg.get_content()
    shot, kind = routes.send(smtp, CART, {**env, "SMTP_PASSWORD": "wrong"}, smtp=FakeSMTP)
    assert kind == "auth"


def _stream(*events) -> str:
    return "\n".join(json.dumps(e) for e in events)


INIT = {"type": "system", "subtype": "init", "mcp_servers": [{"name": "slack", "status": "connected"}]}


def _call(name, args, result="posted", error=False, uid="t1"):
    return [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": uid, "name": name, "input": args}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": uid,
                                                      "content": [{"type": "text", "text": result}], "is_error": error}]}}]


def test_the_carrier_is_judged_by_its_events_not_its_words():
    args = {"channel_id": "C01", "text": "hi"}
    ok = carrier.read(_stream(INIT, *_call("mcp__slack__post_message", args), {"type": "result", "total_cost_usd": 0.002}),
                      "slack", "mcp__slack__post_message", args)
    assert ok.ok and ok.answer == "posted" and ok.cost == 0.002 and ok.servers == ["slack"]
    changed = carrier.read(_stream(INIT, *_call("mcp__slack__post_message", {**args, "text": "pwned"})),
                           "slack", "mcp__slack__post_message", args)
    assert not changed.ok and "changed the arguments" in changed.error
    two = carrier.read(_stream(INIT, *_call("mcp__slack__post_message", args), *_call("mcp__slack__post_message", args, uid="t2")),
                       "slack", "mcp__slack__post_message", args)
    assert not two.ok and "2 calls" in two.error
    learning = carrier.read(_stream(INIT, *_call("mcp__slack__post_message", args)), "slack")
    assert learning.ok and learning.tool == "mcp__slack__post_message" and learning.args == args
    refused = carrier.read(_stream(INIT, *_call("mcp__slack__post_message", args, "channel_not_found", True)), "slack")
    assert not refused.ok and refused.kind == "path" and refused.error == "channel_not_found"
    other = carrier.read(_stream({"type": "system", "subtype": "init", "mcp_servers": [{"name": "Slack", "status": "connected"}]}),
                         "slack")
    assert other.kind == "auth" and "set to: Slack" in other.error
    login = carrier.read(_stream({"type": "system", "subtype": "init", "mcp_servers": [{"name": "slack", "status": "needs-auth"}]}),
                         "slack")
    assert login.kind == "auth" and "needs-auth" in login.error


def test_the_server_chooses_its_carrier_not_the_ork():
    servers = {"slack": ["codex", "claude"]}
    on = {"claude": True, "codex": True}
    assert carrier.choose("slack", servers, on, {}) == ("claude", "")       # codex cannot be held to one tool yet
    who, why = carrier.choose("slack", {"slack": ["codex"]}, on, {})
    assert who == "" and "Codex" in why and "cannot" in why
    who, why = carrier.choose("slack", {"slack": ["claude"]}, {"claude": False}, {})
    assert who == "" and "Claude Code" in why and "off" in why
    assert carrier.choose("claude_ai_slack", {}, on, {}, main="claude") == ("claude", "")   # a connector: the main tool
    assert carrier.choose("slack", servers, on, {}, via="codex")[0] == ""


def test_a_learning_shot_sends_the_cart_and_a_known_call_its_arguments():
    known = carrier.prompt("slack", "mcp__slack__post_message", {"text": "hi"}, "", CART)
    assert "<arguments>" in known and "<cart>" not in known
    held = carrier.prompt("slack", "mcp__slack__post_message", None, "post the notes", CART)
    assert "<cart>" in held and "the tool `mcp__slack__post_message`" in held and "post the notes" in held
    free = carrier.prompt("slack", "", None, "", CART)
    assert "exactly one tool of that server" in free


def test_claude_carries_held_to_its_tools():
    h = harnesses.need("claude")
    argv = h.call("p", "/tmp", ["mcp__slack__post_message"], "laborer")
    assert h.carries and argv[argv.index("--allowedTools") + 1] == "mcp__slack__post_message"
    assert "Bash" in argv[argv.index("--disallowedTools") + 1] and "stream-json" in argv
    assert not harnesses.need("codex").carries and harnesses.need("codex").call("p", "/tmp", ["x"]) is None

    def run(argv, cwd, env):
        assert argv[argv.index("--allowedTools") + 1] == "mcp__slack" and "notes" in argv[2]
        return subprocess.CompletedProcess(argv, 0, _stream(INIT, *_call("mcp__slack__post_message", {"text": "x"})), "")

    c = carrier.carry("claude", "slack", "", None, "post the notes", CART, Path("/tmp"), run=run)
    assert c.ok and c.tool == "mcp__slack__post_message"


SERVER = r'''
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        print("a server's own chatter", flush=True)
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": "2025-06-18", "capabilities": {}}}), flush=True)
    elif msg.get("method") == "tools/call":
        args = msg["params"]["arguments"]
        if args.get("channel") == "nope":
            out = {"content": [{"type": "text", "text": "channel_not_found"}], "isError": True}
        else:
            out = {"content": [{"type": "text", "text": "posted " + args["text"] + " " + __import__("os").environ["TOKEN"]}]}
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": out}), flush=True)
'''


def test_a_local_server_is_found_by_name_and_called_without_a_model(tmp_path: Path, fake_repo: Path):
    (tmp_path / "srv.py").write_text(SERVER)
    (fake_repo / ".mcp.json").write_text(json.dumps({"mcpServers": {
        "Slack": {"command": sys.executable, "args": [str(tmp_path / "srv.py")], "env": {"TOKEN": "${SLACK_T:-none}"}},
        "remote": {"type": "http", "url": "https://mcp.example.com"}}}))
    home = tmp_path / "home"
    home.mkdir()
    launch = mcp.launch("slack", home, fake_repo)
    assert launch is not None and launch.command == sys.executable and launch.where.endswith(".mcp.json")
    assert mcp.launch("remote", home, fake_repo) is None and mcp.launch("ghost", home, fake_repo) is None
    c = local.call(launch, "post_message", {"channel": "C01", "text": "hi"}, environ={"SLACK_T": "tok"})
    assert c.ok and c.answer == "posted hi tok"
    c = local.call(launch, "post_message", {"channel": "nope", "text": "hi"}, environ={})
    assert not c.ok and c.kind == "path" and c.error == "channel_not_found"
    gone = mcp.Launch("x", str(tmp_path / "no-such-binary"), (), (), "here")
    assert local.call(gone, "t", {}).kind == "other"
