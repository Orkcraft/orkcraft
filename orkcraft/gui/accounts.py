"""Settings → Accounts in the GUI (js/accounts.js, docs/design/google-account.md): a personal Google account,
signed in once, heard by External listeners (Gmail), shown by the Calendar (its events, and New event adds
there) and read by the Wiki (Drive). The onboarding's last card opens the same wizard.

The person makes their own OAuth client in Google Cloud (the wizard links each page of the console), pastes
its id and secret, and signs in in the browser; realm/google.py keeps the sign-in as a login on this machine.
`google.use` then puts it in the town's buildings, raising one that is missing; `google.disconnect` revokes it
at Google and forgets it here (the buildings say *sign in again* until it is back or taken out of them).

    host.commands.update(accounts.commands(host))
"""
from __future__ import annotations

from typing import Any, Callable

from orkcraft.gui import builder
from orkcraft.realm import google, logins, shelves

USES = {"gmail": "watchtower", "calendar": "war_drum", "drive": "scrolls"}     # a part → the type that uses it
TITLES = {"watchtower": "External listeners", "war_drum": "Calendar", "scrolls": "Wiki"}


class AccountsError(Exception):
    """A step that cannot be taken; its text is shown to the person."""


class Accounts:
    def __init__(self, host) -> None:
        self.host = host
        self.consent: google.Consent | None = None

    # -- what the page sees ------------------------------------------------------------------------

    def _first(self, type_id: str) -> str:
        return next((b.id for b in self.host.town.scroll.buildings
                     if not b.demolished and self.host.type_of(b.id) == type_id), "")

    def _uses(self, ref: str) -> list[dict]:
        """The buildings that use the account under `ref`: its id, title and which part."""
        name = ref[len(logins.PREFIX):]
        out = []
        for b in self.host.town.scroll.buildings:
            if b.demolished:
                continue
            spec = self.host.town.spec_of(b.id) or {}
            cfg, kind = spec.get("config") or {}, self.host.type_of(b.id)
            part = ""
            if kind == "watchtower" and any(f"login={ref}" in str(x) for x in cfg.get("feeds") or []):
                part = "gmail"
            elif kind == "war_drum" and cfg.get("google") == ref:
                part = "calendar"
            elif kind == "scrolls" and any(str(s).split("/")[0] == f"gdrive:{name}" for s in cfg.get("sources") or []):
                part = "drive"
            if part:
                out.append({"id": b.id, "title": spec.get("title") or b.id, "part": part,
                            "folder": self._folder_of(cfg, name) if part == "drive" else ""})
        return out

    @staticmethod
    def _folder_of(cfg: dict, name: str) -> str:
        spec = next((str(s) for s in cfg.get("sources") or [] if str(s).split("/")[0] == f"gdrive:{name}"), "")
        return spec.partition("/")[2]

    def list(self, args: dict | None = None) -> dict[str, Any]:
        c = google.client()
        return {
            "client": {"id": c["id"]} if c else None,
            "accounts": [{**a, "uses": self._uses(a["ref"])} for a in google.accounts()],
            "consent": self.consent.snapshot() if self.consent else None,
            "links": google.LINKS, "fallback": google.FALLBACK, "what": google.WHAT,
            "standing": {p: bool(self._first(t)) for p, t in USES.items()},
        }

    # -- the wizard ----------------------------------------------------------------------------------

    def set_client(self, args: dict) -> dict[str, Any]:
        try:
            google.save_client(str(args.get("id") or ""), str(args.get("secret") or ""))
        except (google.GoogleError, ValueError) as e:
            raise AccountsError(str(e)) from None
        return self.list()

    def forget_client(self, args: dict) -> dict[str, Any]:
        google.forget_client()
        return self.list()

    def connect(self, args: dict) -> dict[str, Any]:
        """A new sign-in: the URL to open in the browser; Google's answer comes back to this machine."""
        parts = [p for p in args.get("parts") or google.PARTS if p in google.PARTS]
        if self.consent is not None:
            self.consent.cancel()
        try:
            self.consent = google.Consent(parts).start()
        except (google.GoogleError, OSError) as e:
            raise AccountsError(str(e)) from None
        return self.list()

    def cancel(self, args: dict) -> dict[str, Any]:
        if self.consent is not None:
            self.consent.cancel()
            self.consent = None
        return self.list()

    def use(self, args: dict) -> dict[str, Any]:
        """Put the account in the town: Gmail in External listeners, its calendar in the Calendar, Drive in the
        Wiki; a building that is not there is raised. Only the parts asked for and allowed by Google."""
        email = str(args.get("email") or "")
        ref = google.ref_of(email)
        allowed = google.parts_of(ref)
        if not allowed:
            raise AccountsError("That Google account is not connected here")
        parts = [p for p in args.get("parts") or allowed if p in allowed]
        done = []
        for part in parts:
            bid = self._first(USES[part])
            if not bid:
                try:
                    bid = builder.build(self.host, {"type": USES[part]})
                except builder.BuildError as e:
                    self.host.town.toast(f"{TITLES[USES[part]]}: {e}", title="Google", severity="warning")
                    continue
            worker = self.host.town.worker(bid)
            if worker is None:
                continue
            if getattr(self, f"_use_{part}")(worker, ref):
                done.append(TITLES[USES[part]])
        if done:
            self.host.town.toast(f"{email} is used by {', '.join(done)}", title="Google")
        if self.consent is not None and self.consent.state != "waiting":
            self.consent = None
        self.host.on_change()
        return self.list()

    @staticmethod
    def _use_gmail(worker, ref: str) -> bool:
        lines = [str(x) for x in worker.config.get("feeds") or []]
        if any(f"login={ref}" in x for x in lines):
            return True
        ok = worker.save_config({"feeds": [*lines, f"gmail: login={ref}"]})
        if ok:
            worker.refresh_data()                   # the first look marks what is there as seen
        return ok

    @staticmethod
    def _use_calendar(worker, ref: str) -> bool:
        ok = worker.config.get("google") == ref or worker.save_config({"google": ref})
        if ok:
            worker.refresh()
        return ok

    def _use_drive(self, worker, ref: str, folder: str = "") -> bool:
        name = ref[len(logins.PREFIX):]
        cfg = worker.config
        mine = f"gdrive:{name}"
        specs = [str(s) for s in cfg.get("sources") or []]
        if not specs:          # the folders it read by themselves stay its sources
            specs = [str(s) for s in cfg.get("paths") or []] or shelves.default_bases(self.host.town.repo_root)
        specs = [s for s in specs if s.split("/")[0] != mine] + [mine + (f"/{folder}" if folder else "")]
        ok = worker.save_config({"sources": specs, "paths": None})
        if ok:
            worker.refresh()
        return ok

    def folders(self, args: dict) -> list[dict]:
        """The folders of My Drive (or of `parent`), to pick the one the Wiki reads."""
        try:
            return google.drive_folders(google.ref_of(str(args.get("email") or "")), str(args.get("parent") or "root"))
        except google.GoogleError as e:
            raise AccountsError(str(e)) from None

    def set_folder(self, args: dict) -> dict[str, Any]:
        """The Wiki reads one folder of Drive (`folder`, an id) or the whole Drive (empty)."""
        ref = google.ref_of(str(args.get("email") or ""))
        if "drive" not in google.parts_of(ref):
            raise AccountsError("This sign-in may not read Drive")
        bid = str(args.get("building") or "") or self._first("scrolls")
        worker = self.host.town.worker(bid) if bid else None
        if worker is None:
            raise AccountsError("No Wiki here: use Drive in the town first")
        folder = str(args.get("folder") or "").strip()
        if folder and not all(ch.isalnum() or ch in "-_" for ch in folder):
            raise AccountsError("That is not a Drive folder")
        self._use_drive(worker, ref, folder)
        return self.list()

    def disconnect(self, args: dict) -> dict[str, Any]:
        """Revoke at Google and forget here; with `detach`, also take it out of the buildings."""
        email = str(args.get("email") or "")
        ref = google.ref_of(email)
        if args.get("detach"):
            self._detach(ref)
        if not google.disconnect(email):
            raise AccountsError("That Google account is not connected here")
        self.host.town.toast(f"{email}: disconnected. Google no longer gives Orkcraft access", title="Google")
        self.host.on_change()
        return self.list()

    def _detach(self, ref: str) -> None:
        name = ref[len(logins.PREFIX):]
        for use in self._uses(ref):
            worker = self.host.town.worker(use["id"])
            if worker is None:
                continue
            cfg = worker.config
            if use["part"] == "gmail":
                worker.save_config({"feeds": [x for x in cfg.get("feeds") or [] if f"login={ref}" not in str(x)]})
            elif use["part"] == "calendar":
                worker.save_config({"google": None})
            else:
                worker.save_config({"sources": [s for s in cfg.get("sources") or []
                                                 if str(s).split("/")[0] != f"gdrive:{name}"] or None})
            if use["part"] != "gmail":
                worker.refresh()

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"accounts.list": self.list, "google.client": self.set_client, "google.forget_client": self.forget_client,
                "google.connect": self.connect, "google.cancel": self.cancel, "google.use": self.use,
                "google.folders": self.folders, "google.folder": self.set_folder, "google.disconnect": self.disconnect}


def commands(host) -> dict[str, Callable[[dict], Any]]:
    host.accounts = Accounts(host)
    return host.accounts.commands()
