# Import calendar

The Calendar (War Drum) has read one calendar since it was built: its `ics` setting, a `.ics` file or a URL,
or the feeds of `~/.config/orkcraft/calendars.json`. **Import calendar** adds more calendars from its window:

- **A file (.ics)**: an export from Google, Apple or Outlook Calendar, picked or dropped. It is taken in once.
- **A link (iCal address)**: a calendar's secret address in iCal format. The Calendar subscribes to it and
  fetches it again every 15 minutes to once a day (30 minutes by default).

The events of an imported calendar are the Calendar's like any other. They get `calendar.event_upcoming`
(`meeting soon`) and a meeting document, the Wiki keeps items for them ([wiki-librarian.md](wiki-librarian.md)
§6), and `calendar.event_added` / `calendar.event_removed` go out when a refresh changes them.

## 1. Reading a calendar

`sources/ics.py` reads every calendar, imported or not. With the `calendar` extra
(`pip install 'orkcraft[calendar]'`: `icalendar` + `recurring-ical-events`) a calendar is read as RFC 5545
says:

- every RRULE, RDATE and EXDATE;
- an occurrence moved or cancelled on its own (RECURRENCE-ID, STATUS:CANCELLED);
- VTIMEZONE, IANA zone names and the Windows zone names Outlook writes (`W. Europe Standard Time`), across
  a change of summer time.

Without the extra, the standard-library parser of before still reads a calendar. It covers the common
RRULEs, EXDATE and STATUS:CANCELLED, but repeats a series in local time, so across a change of summer time
the hour may slip. A broken calendar the library will not read goes to that parser too.

Either way, times are local and naive, an event shows on the day it starts, and each occurrence of a series
is its own meeting (`meet_id`: its UID and start).

## 2. Keeping them (realm/calendar_imports.py)

The building's `imports` setting lists them by id, with no secret in it:

```json
"imports": {"3fa9c1": {"kind": "file", "name": "Offsite"},
            "8b20de": {"kind": "link", "name": "Work", "secret": "keychain:calendar.drum.8b20de",
                       "host": "calendar.google.com", "every": 30}}
```

- Each calendar's copy is `.orkcraft/war_drum/<building>/imports/<id>.ics`. For a link it is the last
  good fetch. `status.json` beside it says when each one was fetched, how many events it holds and what
  went wrong.
- **A secret link is access to the calendar**: whoever has it reads the calendar. It goes to
  `realm/logins.py`, like the Watchtower's tokens: the OS keychain when `keyring` is installed, else a
  0600 file out of the project. The setting keeps only the reference and the host. A spec whose link
  holds anything but a `keychain:` reference is refused (`catalog_checks.py`), so a link pasted into the
  settings by hand never lands in the town scroll.
- The link is never sent back to the page, never in a toast, an error or the chronicles. A failed fetch
  says why in plain words ("HTTP 404: it may have been reset — copy the secret address again").
- A link typed into the old `ics` field becomes a subscription the same way. A town that kept a plain link
  there before still reads it, and the page shows it by its host alone.
- Removing an import deletes its copy, its status and its secret.

## 3. The window: a page in steps over Info

Import calendar is in the Calendar's Info, beside New event and Prepare doc, and in its settings (Work).
It opens a page over the Info, not a dialog (`js/infopage.js`):

1. **Import calendar**: *A file (.ics)* or *A link (iCal address)*; Cancel.
2. **Import a file**: the drop zone (or Choose a file) and its name. **Subscribe to a link**: where Google,
   Apple and Outlook give the address, the link (a password field), its name, how often it is updated.

Every step after the first has **← Back** in the window's top right; Escape goes back too. Once a calendar
is imported a toast says how many events it brought, and the Info is the usual one again. The settings list
each import with its kind, its host, how often it is updated, when it was last fetched, and Remove; Update
now fetches every link at once.

`js/infopage.js` is shared: any type may open a page of its own over its Info (`openInfoPage`) and draw it
from `infoPage(b, page)`, with `infoActs(b)` for the actions only its Info offers (`js/types.js`).

## 4. Not done

- Writing back to a subscribed calendar: New event still goes to the `ics` file, or the building's own
  `local.ics`.
- CalDAV, and logging in to Google or Microsoft (OAuth). An iCal address needs neither.
