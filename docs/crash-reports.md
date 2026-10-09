# Crash reports

When something breaks in Orkcraft, a report says **where in Orkcraft's own code** it broke, so it can
be fixed. Crash reports share one answer with the [usage stats](usage-stats.md): **off until you say
yes**, in the window, the installer or Settings (`orkcraft usage on|off`).

## What a report holds

- the error's type (`KeyError`, `TypeError`…) and its message with everything that could be yours
  taken out: paths, URLs, e-mail addresses and anything in quotes become `<path>`, `<url>`,
  `<email>`, `'…'`;
- the stack: for each line, the file **in Orkcraft** (`orkcraft/gui/host.py`) or the library
  (`websockets/server.py`), the function and the line number. A line in any other file — your
  project, a script of yours — is only `<other>`, with no name;
- where it happened: an error nobody caught, on a thread, in the server's loop, in a command of the
  window, in the town's clock, or in the window's page;
- the Orkcraft version, the OS (darwin · linux · windows), the Python version, and the same random
  install id as the usage stats.

**Never sent:** local variables, your code, prompts, what the orks or you wrote, logs, file, project
or building names, your IP address.

At most 20 reports per run, and the same error once.

## Sessions

Each run of the window is also a *session*: it starts, and ends as *exited*, *crashed* (an error
nobody caught), or *abnormal* (the process died without closing; found when the next run starts).
A session carries only its random id, its start, how long it ran and how many errors it had. That
is how we see the share of runs of each version that ended well.

## Where it goes

To Orkcraft's own proxy, the same Cloudflare Worker as the usage stats
([tools/usage-worker/](../tools/usage-worker/), `POST /v1/crash`). It checks every field again,
keeps only the ones above, drops your IP address and passes the report to
[Sentry](https://sentry.io/) (US data centre).

## On your machine

Whatever you answered, each crash's full traceback is written to `~/.orkcraft/crashes/` (the last 30),
on your machine only: attach one to an issue if you like. `ORKCRAFT_USAGE_DEBUG=1 orkcraft` prints
every report instead of sending it. Nothing is sent while `DO_NOT_TRACK=1` or
`ORKCRAFT_NO_USAGE=1` is set, under CI, or in the demo.

The code: [`orkcraft/core/crashes.py`](../orkcraft/core/crashes.py) (what a report holds, the
scrubbing) and [`js/crashes.js`](../orkcraft/gui/static/js/crashes.js) (the window's errors).
