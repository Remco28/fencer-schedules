# Fencer Schedules — living product spec

**Status:** Discovery closed for v1 regional/national. Do not scaffold until Frank says go.
**Date:** 2026-08-19
**Incoming brief:** `revive-spec.md` (Buffy interview with Frank). Legacy app is reference only.

## Decisions

| Topic | Call | Status |
| --- | --- | --- |
| Job | Show **who from our club fences when** so coaches / parents / teammates can support them — **including days before the event** | Locked |
| v1 ship | **Phone start list and a downloadable PDF of that same list.** | Locked 2026-08-19 |
| v1 cut | **Start list only.** No strips, results, or fencing-now. FTL is too late for the pre-event PDF. | Locked |
| Pre-event PDF | **Core.** Pick a tournament → download a PDF → Frank texts/emails it himself as a club reference. | Locked 2026-08-19 |
| PDF contents | Same grouping as the phone: day → event → tracked fencers, club shown. **Day + event + names is enough.** Clock start time **if the source has it**; omit if not. | Locked 2026-08-19 |
| Users | Single operator. **No app accounts.** PDF recipients are not app users. | Locked |
| Codebase | **Fresh rebuild.** Old code is reference only. | Locked |
| Surface | Phone web for the list; PDF download for distribution. | Locked |
| Stack | **Python + FastAPI + SQLite + Jinja2**, local | Locked |
| Search | **One box.** Prefer USFA hits for regional/national; AskFRED for the rest. | Locked 2026-08-19 |
| Fencer names | **USFA** when AskFRED `registration_url` points at `member.usafencing.org`. AskFRED **preregistrations HTML** has local names but the **API does not**; local names are **nice-to-have, not v1**. | Locked 2026-08-19 |
| FencingTracker | Out of v1 | Locked |
| FTL in v1 | **Not required.** Frank will still create a free FTL account in gitignored `.env` for later. Never paste the password in chat. | Locked |
| Club identity | Match **Elite Fencers Club** / **Elite FC**. **Never match `EFC`** — that is *Elite Fencing Club*. | Locked 2026-08-19 |
| Club config | Gitignored config file. No settings page. | Locked |
| Extra fencers | Search the **loaded local list** (no API). Or open an event roster and tap Track. Untrack from the schedule or roster. | Locked 2026-08-19 |
| Event roster | Tap an event to see every name; tap to track/untrack | Locked 2026-08-19 |
| Clock | USFA card time is the **event start**. Show it as a time only. | Locked 2026-08-19 |
| Layout | **One scroll:** day → events (by start time when known) → tracked fencers | Locked |
| Time grain | Event clock time when present. Not per-fencer pool/DE times. | Locked |
| Refresh | Re-fetch entries, then regenerate PDF. No live polling. | Locked |
| After the event | Auto-purge (~48h TTL), or Remove by hand. | Locked |
| Multiple tournaments | Keep several loaded lists. Switch locally. Re-fetch only on first open or Refresh. | Locked 2026-08-19 |
| Host | Local / self-hosted | Locked |
| Anti-bot | Polite requests, cache, rate limits. Captcha workarounds within reason. | Locked |
| First tournament | Trick or Retreat ROC / RJCC — USFA `12013` (`member.usafencing.org/details/tournaments/12013`), AskFRED `f4fbfddf-8316-46d2-9392-8a8245059f86`, Aug 22–23, Edison NJ. Regional → **USFA names**. Example, not a hard ship date. | Locked |

## Vocabulary

| Word | Meaning here |
| --- | --- |
| Club fencer | Competitor whose club is **Elite Fencers Club** / **Elite FC** |
| Tracked fencer | Club fencer **or** someone added by hand |
| Event | One weapon/age/rating slice (e.g. Cadet Men's Foil) |
| Start list | Who is entered in which event, on which day, with a clock time only if published |
| Club schedule PDF | Downloadable copy of that start list, sent around **before** the tournament |
| Regional / national | USFA-managed (ROC, RJCC, NAC, SYC, …). **USFA names win.** |
| Local | Division / club events. AskFRED catalog + event times. **Names not in the API** (HTML `/preregistrations` only). |
| Live status | Strips / results / fencing-now — **not v1** |

## Outline / non-goals

**v1:** one search box → one tournament → phone list of EFC + picks → download the same thing as a PDF.

**Not v1**

- Strips, results, fencing-now, FTL as a gate
- Local club names via AskFRED `/preregistrations` HTML (captcha; API 404)
- FencingTracker, app accounts, settings page, email-from-the-app
- Notifications, auto-refresh, history, multi-tournament
- Weapon filter, per-fencer home cards
- Reusing the old app in place

## Functions & interaction

One list. PDF is an export of that list.

| Function | Kind |
| --- | --- |
| Search upcoming (one box) | Empty state |
| Day-sectioned start list | The phone page |
| Track additional fencer | Overlay; included in PDF |
| Download PDF | Verb on the loaded tournament |
| Club name + aliases | Gitignored config |

**Anti-pattern:** two-table split.

## User stories

### 001 — Find a tournament and see our club's start list

As a coach/parent on a phone, I want one search box, a pickable upcoming tournament, and Elite Fencers Club fencers under each event by day, so I know who to watch when.

**Acceptance**

- [ ] One search box. Regional/national hits prefer USFA; locals come from AskFRED.
- [ ] Picking a result loads it. Names come from USFA if USFA has that tournament, else AskFRED.
- [ ] EFC fencers appear under their events, grouped by day; clock time only if the source has it.
- [ ] Every fencer row shows that fencer's club.
- [ ] “Track additional fencer” adds someone to the same lists.
- [ ] No strip / result / live-status chrome.

### 003 — Hand the club a schedule PDF before the event

As the operator, I want to download a PDF of that same list days before the tournament, so I can send it to the club while FTL still has nothing.

**Acceptance**

- [ ] One action downloads a `.pdf` (Frank sends it himself).
- [ ] Same grouping and people as the phone list, including extra tracked fencers.
- [ ] Day + event + names is complete; clock times appear only when known.
- [ ] Trick or Retreat uses the **USFA** entry list.
- [ ] A local tournament (when we have an example) uses **AskFRED**.
- [ ] Re-fetch + download again after entries change.

### 002 — Live day-of status

Deferred.

## Not writing yet

- Code, deps, scaffold, `.hermes/plans/` until Frank says go
- Treating USFA or AskFRED access as unproven (they are proved for v1)
- Implementation until Frank says go

Plan: `.hermes/plans/2026-08-19_184446-v1-start-list.md`

**Working assumptions — update 2026-08-19, see `FEASIBILITY.md`**

- **USFA entries: proved public.** Names + `Elite Fencers Club`.
- **AskFRED API: catalog + events proved.** Token in gitignored `.env`. `name_eq` is exact/case-sensitive only. `registration_url` pointing at USFA is the auto-route signal.
- **AskFRED API: no entry lists.** Local club names are **not available** the official way. Do not scrape the captcha page.

## How we use this file

1. New call from Frank goes in **Decisions** first.
2. Stories are rewritten to match.
3. `revive-spec.md` is the interview record. This file is what we build against.
4. Chat stays shorter than this file.

## Human leftover (not blocking v1)

- Create a free FencingTimeLive account later; credentials only in gitignored `.env`.
