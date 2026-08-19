# Feasibility — source access

**Date:** 2026-08-19
**Scope:** Can we get start-list data for v1 (search + events + names + club + day)?
**Not in scope:** FTL live strips/results (deferred).
**Secrets:** AskFRED token is in gitignored `.env` as `ASKFRED_API_TOKEN`. Never commit, never paste in chat.

## Matrix

| Source | Need | Accessible? | Method | Auth | Risk | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| **USFA** | Regional/national events + entries with club | **Yes** | Public HTML + `GET /details/tournaments/{id}/entrants?event_id=` | None | Polite rate | **Easy** |
| **AskFRED HTML** | Anything | Captcha wall from this host | Do not scrape | — | reCAPTCHA | **Cut** |
| **AskFRED API** | Catalog + events | **Yes** (token works) | `GET /api/v1/tournaments` + `.../events` | Bearer in `.env` | ~125 req/hour | **Easy for catalog/events** |
| **AskFRED API** | Who is entered (local names) | **No** — documented endpoints only; guessed `/entries` `/registrations` `/competitors` `/fencers` `/preregs` are 404 | Official API only | Bearer | — | **Missing. Local names blocked.** |
| **FTL** | Live strips | Login wall | Later | `.env` later | Unknown | **Later** |

## USFA — proved

Trick or Retreat = `12013`.

- Page lists Sat Aug 22 / Sun Aug 23, 30 events, **close of registration** (not bout start).
- `GET .../entrants?event_id=72823` → names, rating, **club**, division, membership #, Approved. No login.
- Club on rows: `Elite Fencers Club`. Frank confirmed match **Elite FC** / **Elite Fencers Club**. Do **not** match `EFC` (that is *Elite Fencing Club*).

## AskFRED API — proved 2026-08-19 with the project token

Base: `https://www.askfred.net/api/v1/`  
Docs: https://help.askfred.net/en/articles/10328385-api-endpoints-data

| Call | Result |
| --- | --- |
| `GET /me` | 200. Token valid. |
| `GET /tournaments?name_eq=Trick or Retreat ROC / RJCC` | 200, 1 hit. **Exact official name, case-sensitive.** Lowercase → 0 hits. Partial `Trick or Retreat` → 0 hits. |
| `name_start` / `name_matches` / `q` / `name` | **Ignored.** Returns unfiltered first page (~53k tournaments). |
| `GET /tournaments/:id` | 200. Dates, venue, timezone. |
| `registration_url` on regionals/nationals | Points at `member.usafencing.org/details/tournaments/{id}` (Trick or Retreat → `12013`; October NAC → `12312`). |
| `registration_url` on locals | AskFRED `/preregister` URL, not USFA. |
| `GET /tournaments/:id/events?per_page=50` | 200, 30 events. `full_name`, weapon, gender, `close_of_registration`. Default page size 10. |
| `GET /tournaments/:id/entries` (and registrations/competitors/fencers/preregs) | **404** |
| `GET /events/:id` and `.../entries` | **404** |
| `?include=events` / `include=registrations` | Ignored. |
| `usfa_event_level=regional` + date window | Works (3 regionals in 19–31 Aug 2026, including Trick or Retreat). |
| Upcoming `start_date_gteq=2026-08-19` + `end_date_lteq=2026-09-30` | **235** tournaments (~5 pages at `per_page=50`). |

**Search implication:** the API has **no working substring parameter**. `name_eq` is exact official name, case-sensitive. Practical search: fetch a dated upcoming window and filter names client-side (cache it). Proved 2026-08-19: window 19 Aug–15 Sep = 167 tournaments / 4 pages; substring `wanglei` hits *Wanglei Summer Cup III: Youth & Senior Open* (`07060a1f-…`) plus another Wanglei event.

**Local tournament probe** `07060a1f-1e22-4db1-b6f6-a7f0d956d877` (Wanglei Summer Cup III, Plainsboro NJ, 29 Aug):

- `GET /tournaments/:id` and `.../events` work. 3 events, close-of-reg times, `registration_url` is AskFRED preregister (not USFA) → correctly local.
- Exact `name_eq` of the full official title works. `Wanglei` / `Wanglei Summer` as `name_eq` return 0.
- Every entries/prereg/competitors path still **404**. Finding the tournament ≠ getting who is entered.

**Auto-route implication:** if `registration_url` contains `member.usafencing.org`, take names from USFA. That is how we know “USFA has this tournament.”

**Local names:** the human page `/tournaments/{id}/preregistrations` is the list. From this host that URL is captcha-walled. Official API paths for it are **404**. Nice-to-have later (browser session or AskFRED adding the endpoint). Not a v1 gate.

## FTL — later

Homepage → `/account/login`. Free account. Not a v1 gate.

## Open product call

Local tournaments: we can search them and list events/days. We **cannot** list who from Elite FC is entered via the official API.

## Do not do

- Scrape AskFRED HTML through the captcha.
- Print or commit the token.
- Match `EFC` on USFA.
- Treat FTL as a v1 blocker.
