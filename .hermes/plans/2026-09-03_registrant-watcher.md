# Registrant Watcher — Implementation Plan

**Author:** Hermes (ThinkPad session) · **Date:** 2026-09-03
**For:** A Hermes agent implementing this cold from a fresh clone (no conversation context).
**Status:** Ready to execute.

---

## 1. Goal

Add a watcher to the fencer-schedules app that, twice a day, re-checks saved tournaments for
**new registrants** and emails the club when someone new signs up. Two notification modes:

1. **Club watch (per tournament):** email when a fencer from *our club* joins **any event** in
   that tournament.
2. **Event watch (per event):** email when **anyone** joins a specific event — for small local
   tournaments, where knowing whether *anybody* signed up decides whether we attend.

One email per tournament per run, only when there are new names. Silent when nothing changed.

---

## 2. Context (read before coding)

- Repo: `git@github.com:Remco28/fencer-schedules.git`, branch `main`. Working tree must be clean.
- Stack: Python 3.12, uv, FastAPI, SQLAlchemy, SQLite, Jinja2. Tests: `uv run pytest tests/ -q` (40 passing as of 2026-09-03). Run app: `./run.sh` → http://127.0.0.1:8765.
- The app already fetches fresh registrant names:
  - **USFA events** (`tournament.usfa_id` set): names from `fencer_schedules/sources/usfa.py`
    (`UsfaClient.fetch_entrants`, public HTML/JSON — no login).
  - **Local events** (no usfa_id): names from AskFRED's *logged-in* preregistrations HTML
    (`fencer_schedules/sources/askfred_prereg.py`, `AskFredSite` — Devise login with
    `ASKFRED_EMAIL`/`ASKFRED_PASSWORD` from `.env`; API has no entries endpoint).
  - `fencer_schedules/load.py::load_tournament(askfred_id, settings, ...)` returns a full
    `Tournament` with events + fencer names. **Reuse it for the watcher.**
- Storage: `fencer_schedules/db.py` `Store` — SQLite, tables `stored_tournaments` (Tournament JSON
  payload), `selection` (current). `create_all` is additive; adding a table is safe for existing DBs.
- Club identity: `fencer_schedules/club.py::is_our_club(club, settings)` — normalized exact match
  against `config.yaml` `club.name` + `club.aliases` (**Elite Fencers Club** / **Elite FC**; never
  EFC). Use it; do not reimplement.
- Settings: `fencer_schedules/config.py` `Settings.load()` reads `config.yaml` + `.env`.
  Existing `.env` keys: `ASKFRED_API_TOKEN`, `ASKFRED_EMAIL`, `ASKFRED_PASSWORD`.
- AskFRED rate limit: **125 API requests/hour**. The watcher reuses `load_tournament` (a few
  requests per watched tournament per run) — fine at 2 runs/day. **Do not** call `search()`
  (window scan) in the watcher.
- AgentMail: the machine already uses the AgentMail REST API/SDK (see `~/backup-monitor-plan.md`
  §3–4.1): Python SDK `agentmail`, inbox-scoped API key in `.env`, send via `messages.send()`.
  No IMAP. No MCP.

---

## 3. Design

### 3.1 New DB table: `watches`

| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `askfred_id` | str | tournament |
| `event_id` | str, nullable | NULL = tournament-wide club watch; set = event watch |
| `notify_kind` | str | `"club"` (club members only) or `"all"` (any registrant) |
| `last_seen` | JSON text | dict `{event_id: [["Name, First","Club"], ...]}` — snapshot for diffing |
| `updated_at` | datetime | |

One row per (askfred_id, event_id, notify_kind). Toggling a watch on = upsert; off = delete.

**Baseline rule (critical):** the first time a watch is evaluated for an event, store the current
names as `last_seen` and **do NOT email** — otherwise every existing registrant looks "new".
Emails only on names present now but absent in `last_seen`.

### 3.2 New module: `fencer_schedules/monitor.py`

- `def run(settings, store, dry_run=False) -> list[str]` — the whole job; returns email subjects sent.
  1. `for watch in store.watches()`:
  2. `t = store.get(watch.askfred_id)`; if None (expired/removed) → `store.delete_watches(askfred_id)`, skip.
  3. `fresh = load_tournament(t.askfred_id, settings)` — may raise (login/captcha/network) →
     log to `monitor.log` via `logging`, **continue** (never abort the whole run).
  4. For each watched event (see 3.3): compute `new = names(fresh) - last_seen[event_id]`.
  5. If any `new`: build digest (see 3.4) → if not dry_run, send; update `last_seen`.
     If none: just update `last_seen`.
  6. Return subjects sent (empty when nothing new / dry run).
- `if __name__ == "__main__":` argparse: `--dry-run` (print digest, no send, no DB write) and
  `--once`. No daemonizing; cron/systemd calls it.
- Test seams: `run` accepts injected `store` (real Store with temp DB path is fine).

### 3.3 Watched events per watch row

- `notify_kind == "club"`, `event_id IS NULL` → every event in the tournament that has any names.
  Filter `new` names by `is_our_club(club, settings)`.
- `notify_kind == "all"`, `event_id` set → just that event (match by `Event.source_event_id`).
  No club filter.

### 3.4 Digest email

- Subject: `New registrants: <tournament name> (N new)`.
- Body: per event with additions — `event.day %A, %B %-d`, `clock` if any, event name, then one
  line per new fencer: `  - Name, First — Club` (+ ` [CLUB]` marker when it's our club).
- From: the AgentMail inbox address. To: `settings.alert_recipient`.

### 3.5 Notify wrapper: `fencer_schedules/notify.py`

- `def send_digest(settings, subject, body) -> None` — thin AgentMail SDK call, keep `send=False`
  guard so dry-run never sends. Import `agentmail` lazily inside the function (test seams).
- Never log/print API key.

### 3.6 UI toggles (minimal)

- Schedule page header/actions: toggle button **"Watch for new Elite FC registrants"** → POST
  `/schedule/watch` (tournament-wide club watch).
- Event roster page: toggle button **"Email me when anyone signs up"** → POST
  `/schedule/events/{event_id}/watch`.
- Both: form POST with hidden `next` back to current page; redirect 303. Template shows on/off
  state from `store.watch_for(...)`.

### 3.7 Scheduling (target machine, user-side)

```cron
0 9,21 * * * cd ~/Dev/fencer-schedules && .venv/bin/python -m fencer_schedules.monitor --once >> monitor.log 2>&1
```

Document in `SETUP.md` (cron + systemd timer alternative). America/New_York times.

---

## 4. Files

**Create:**
- `fencer_schedules/monitor.py`
- `fencer_schedules/notify.py`
- `tests/test_monitor.py`, `tests/test_notify.py`

**Modify:**
- `fencer_schedules/db.py` — `Watch` model (SQLAlchemy DeclarativeBase, same module as
  `StoredTournament`), `Store.watches()`, `Store.watch_for(askfred_id, event_id, notify_kind)`,
  `Store.set_watch(...)`, `Store.save_last_seen(watch, last_seen)`, `Store.delete_watches(askfred_id)`
- `fencer_schedules/config.py` — add `agentmail_api_key`, `agentmail_inbox`, `alert_recipient`
  (+ `.env` parsing in `Settings.load()`)
- `fencer_schedules/app.py` — two POST routes + watch state into template context
- `fencer_schedules/templates/schedule.html`, `templates/event.html`
- `fencer_schedules/static/app.css` — toggle button style (reuse `.btn-track`/`.btn-danger`-like)
- `pyproject.toml` — add `agentmail` dependency
- `.env.example` — add `AGENTMAIL_API_KEY=`, `AGENTMAIL_INBOX=`, `ALERT_RECIPIENT=`
- `SETUP.md` — AgentMail setup + cron lines

---

## 5. Task plan (TDD, bite-sized)

### Task 1: Config
`Settings` + `Settings.load()` parse the three new `.env` keys. Test in `tests/test_config.py`
(create temp `.env`, assert values).

### Task 2: DB Watch model
`Watch` model + Store methods. Tests: `tests/test_db.py` — save/load last_seen, list watches,
delete by tournament, upsert semantics.

### Task 3: Diff logic (pure)
In `monitor.py`: `new_names(last_seen_event, current_event) -> list[Fencer]` (name+club tuple
identity), club filter via `is_our_club`. Tests: `tests/test_monitor.py` — baseline (empty
last_seen → nothing new, but records), same roster → nothing, one new → one, club filter keeps
Elite only (never EFC).

### Task 4: Digest builder
`build_digest(tournament, additions) -> (subject, body)`. Tests: subject has count; body has
event/day/time/names/club marker.

### Task 5: Monitor run loop
`run(settings, store, dry_run=False)` with baseline rule + per-watch error isolation. Tests with a
real `Store` on a temp DB seeded with a saved tournament; monkeypatch `load_tournament` to return
a controlled `Tournament`. Assert: baseline run sends nothing but stores last_seen; second run
with an added fencer sends one email (mock `notify.send_digest`); dry_run sends nothing and does
not write last_seen; a raising `load_tournament` is logged and skipped.

### Task 6: Notify wrapper
`send_digest` with lazy `agentmail` import; dry_run guard. Test with monkeypatched SDK class.

### Task 7: App routes + templates
`POST /schedule/watch`, `POST /schedule/events/{event_id}/watch`, context flags. Tests:
`tests/test_web.py` — toggle on/off, redirect, page shows state.

### Task 8: pyproject + env example + SETUP.md
Add `agentmail`, three `.env.example` keys, cron/systemd section, AgentMail setup steps.
Test: `uv sync` resolves; `uv run python -m fencer_schedules.monitor --dry-run` exits 0 on empty store.

### Task 9: Full suite + commit + push
`uv run pytest tests/ -q` all green → `git add -A && git commit -m "feat: registrant watcher with
AgentMail digests"` → push `main` → verify `git status` clean and
`git rev-parse HEAD == git ls-remote origin refs/heads/main`.

---

## 6. Verification checklist (implementing agent must complete)

- [x] `uv run pytest tests/ -q` — all pass.
- [x] `uv run python -m fencer_schedules.monitor --dry-run` exits 0 with no watches (fresh DB).
- [x] Unit test proves: first run baselines silently (no email, last_seen recorded).
- [x] Unit test proves: added fencer on second run → exactly one digest email, correct subject/body.
- [x] Unit test proves: club watch only emails our club; event watch emails anyone; EFC never matches.
- [x] Unit test proves: a failing `load_tournament` for one tournament doesn't kill the run.
- [ ] Manual (optional, if credentials present in `.env`): load Wanglei (local), enable event
  watch, `--dry-run` prints current roster without sending.
- [x] `git status` clean; pushed; remote SHA matches local HEAD.

---

## 7. Known decisions (do not re-litigate)

- Reuse `load_tournament` for fresh names; no new scraping.
- Baseline-first: never email the full existing roster on first watch.
- One email per tournament per run, only on new names. No email when nothing changed.
- Club watch is tournament-wide (all events); event watch is per-event, anyone.
- Names keyed by (name, club) — no fuzzy matching.
- Watch failures: log + skip; the run never dies on one tournament.
- Scheduling is cron/systemd on the always-on machine — not in-app, not a Hermes cron.
- Secrets stay in gitignored `.env`; never printed, never committed.
- Dry-run never sends and never mutates `last_seen`.

## 8. Open items (user-side, on the target machine)

- [x] AgentMail inbox address + API key → `.env` (`AGENTMAIL_API_KEY`, `AGENTMAIL_INBOX`)
- [x] Recipients live in the app Settings page (default `frankcng@gmail.com`; comma-separated)
- [x] systemd timer 09:00/21:00 America/New_York (`fencer-schedules-monitor.timer`)
