# Design — connections: MCP first for the first wow, a token later as an improvement

Status: decided 2026-10-12 with the owner; nothing built. A rule for every building that reads an outside service:
External listeners ([watchtower-automation.md](watchtower-automation.md)), Metrics
([catalog-shelves.md](catalog-shelves.md) §3a), the Publisher. Priority: the rule is decided now; the offer to move
to a token (§3) is **Later**.

## 1. The trade

An outside service (Sentry, Amplitude, GitHub, Slack, Jira…) can be reached two ways:

| | through the person's AI tools' MCP servers | through the service's own API, with a token |
|---|---|---|
| setting up | nothing, when the MCP server is already on | a login or a token, a few minutes |
| each read | a model call: tokens, and the window's limit | code, free |
| fits | the first session, a first wow | a read that repeats (an hourly chart, a listener) |

## 2. The rule

> **MCP first, for the first wow; a token later, offered as an improvement of the town.**

- **In the first session** a building connects through an MCP server the person already has turned on, with no
  setup. What a person sees in their first fifteen minutes must not wait on a token.
- **The token path is always there** for whoever wants to spend the time from the start: `orkcraft connect` with a
  browser login and the token in the OS keychain ([watchtower-automation.md](watchtower-automation.md)), or the name
  of an environment variable, never the token itself in a setting (the audit already asks this).

## 3. The offer, a few days in (Later)

After a few days of use, the move to a token comes as one of the town's improvements, through Improve, never as a
nag:

- **the Treasurer makes it, with the number:** "the Sentry chart cost $0.84 and 3 % of your Claude window this week
  through MCP; with a token it reads for free" — money and limits are its expertise
  ([town-hall-roles.md](town-hall-roles.md));
- only for a connection that repeats (a schedule, a listener), never for one used once;
- one offer per connection; declined, it does not come back unless the cost doubles.

## 4. What it does to the README's promise

"No API keys" stays true for the start: a person can run the whole town without one. The README says it plainly: a
building may later offer a token for a service it reads often, to make that free; the person decides.
