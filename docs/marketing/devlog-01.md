# Devlog #1 — Building the factory that builds my side project

*Draft for the owner. Post on the devlog (GitHub Discussions or the landing page's blog), then shortened for X,
Bluesky, Mastodon and LinkedIn. One image: `docs/design/img/orkline-camp-concept-v2.png`, captioned "concept art,
placeholder; hand-drawn art is on its way".*

---

All day I review other people's merge requests and sit in calls. On the metro home I take out my phone, and what I
want to open is not a feed. It is my own project, and the agents that have been working on it while I was away.

That is what Orkline is for. It opens your project as a small camp of orks. Work comes in at the edge: an issue on
GitHub, a card on the Task board, something the town's clock starts every morning. It rolls along a line of
buildings, where orks running Claude Code or Codex in your own terminals do the work. It stops at the Review gate,
where nothing goes further without your nod. And then the Publisher catapults it over the wall: a pull request
opened, a post published, a reply sent.

**Why a camp and not a dashboard?** Because the thing I actually want to see is not a list of sessions. It is the
flow: which work is stuck, which ork is waiting for me, and how much each finished thing cost. A camp shows that at a
glance, and it makes an evening of building my own thing feel like playing a factory game instead of doing more work.

**What works today**

- Every ork's state in one place: working, asking you a question, stuck, waiting for a limit to reset; the work it
  is on named.
- Questions come to you pinned on top of the answer, and you answer in one line. While you are at work, the camp
  stays quiet: the orks note their assumptions and keep going where it is safe.
- "Since your last look": when you come back, the first thing you see is what was built, then what waits for you.
- "I'm off": tell the camp you're leaving, set a cap on how much of your limit it may use, and it keeps working
  until evening.
- Office: the same town drawn calm and monochrome, for when you'd rather it looked like work.

**What it is not.** Not a cloud service. No API keys: it runs your own Claude Code and Codex with your own
subscriptions, on your own machine. Open source, Apache 2.0.

**What's next.** Hand-drawn pixel art (the camp you see here is concept art), the phone as a console, and the first
ten testers. If you build your own things with coding agents after work, I'd love you to be one of them: [link].

— the camp of one behind Orkline
