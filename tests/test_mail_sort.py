"""The tower's first sort of a message (realm/mail_sort.py, docs/design/watchtower-mcp-paths.md §12): code tells
mailings and machines' mail without a model, the model reads the rest in one call a batch, code decides."""
from __future__ import annotations

from orkcraft.realm import lookout, mail_sort, watch


def test_mailings_and_machines_are_told_by_code():
    assert mail_sort.automated("GitHub <noreply@github.com>", "CI passed") == "comes from noreply@github.com"
    assert mail_sort.automated("ann@client.io", "Weekly news", ["list-unsubscribe"]) == "has an unsubscribe link"
    assert mail_sort.automated("ann@client.io", "x", ["precedence:bulk"]) == "is a bulk mailing"
    assert mail_sort.automated("ann@client.io", "x", ["CATEGORY_PROMOTIONS"]) == "is in Promotions"
    assert mail_sort.automated("ann@client.io", "Automatic reply: away") == "is an automatic reply"
    # a person, even writing from a shared address, is never taken for a machine
    assert mail_sort.automated("Ann <ann@client.io>", "Re: the invoice") == ""
    assert mail_sort.automated("info@client.io", "Question about the order") == ""
    assert mail_sort.automated("ann@client.io", "x", ["auto-submitted:no"]) == ""


def test_the_verdict_is_code_and_the_careful_side_wins():
    upset = mail_sort.read({"asks": "reply", "urgency": "week", "risk": "low", "tone": "upset", "agent": True})
    assert mail_sort.verdict(upset) == ("high", "person")              # an upset sender always goes to the person
    decision = mail_sort.read({"asks": "decision", "urgency": "week", "risk": "low", "tone": "neutral", "agent": True})
    assert mail_sort.verdict(decision) == ("normal", "person")
    easy = mail_sort.read({"asks": "reply", "urgency": "week", "risk": "low", "tone": "friendly", "agent": True})
    assert mail_sort.verdict(easy) == ("normal", "agent")
    fyi = mail_sort.read({"asks": "info", "urgency": "none", "risk": "none", "tone": "neutral", "agent": True})
    assert mail_sort.verdict(fyi) == ("low", "")                        # it only informs: nobody needs to answer
    odd = mail_sort.read({"asks": "dance", "risk": "?", "agent": "yes"})   # words outside the lists: the careful side
    assert (odd["asks"], odd["risk"], odd["agent"]) == ("reply", "medium", False)
    line = mail_sort.line({**upset, "risk_why": "client may leave"}, "high", "person")
    assert line.startswith("importance: high · answered by: you") and "tone: upset" in line
    assert mail_sort.line({"auto": "has an unsubscribe link"}, "low", "") == \
        "automated: it has an unsubscribe link · importance: low"


def test_the_lookout_sorts_in_the_same_call_and_keeps_everything_without_an_intent():
    asked = []

    def model(prompt, m=None):
        asked.append(prompt)
        return ('{"keep": [{"n": 1, "why": "asks for a quote", "asks": "reply", "urgency": "today", "risk": "medium",'
                ' "tone": "neutral", "agent": true}]}', None)

    sigs = [watch.Signal("t", "mail", "Ann: a quote?", "body"), watch.Signal("t", "mail", "Bob: hi", "body")]
    verdicts, problem = lookout.judge("", sigs, model, triage=True)
    assert problem == "" and len(asked) == 1 and "Rate every message" in asked[0]
    assert [v.kept for v in verdicts] == [True, True]                    # the sort alone keeps every message
    assert (verdicts[0].importance, verdicts[0].answer) == ("high", "agent")    # an answer due today
    assert verdicts[1].sort is None and verdicts[1].importance == ""
    verdicts, problem = lookout.judge("", sigs, None, triage=True)       # no model: all pass, unsorted
    assert all(v.kept for v in verdicts) and problem.startswith("triage:")
