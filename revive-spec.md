# Project Revive — Specification

**Status:** Draft (scope definition + feasibility plan)
**Date:** 2026-08-19
**Author:** Buffy (interview with Frank, project owner)
**Repository:** fencer-schedules-app (legacy, to be treated as reference only)

---

## 1. Purpose of This Spec

The project is a fencing-tournament tracking app that went dormant. The sites it scrapes
(FencingTimeLive, AskFRED, FencingTracker) have since changed how they serve data — FTL now
requires login, AskFRED was rebuilt on a new platform with UUID URLs and bot challenges, and
FencingTracker has become an archival database. The old code's data layer is broken.

This spec captures:

1. **Goal 1 — Feasibility investigation:** Determine whether each of the four target sites
   (FencingTimeLive, AskFRED, FencingTracker, USA Fencing) can still be accessed programmatically,
   and under what conditions.
2. **Goal 2 — Scope redefinition:** What the rebuilt app will do, for whom, and how it will be built.

No code changes are made yet. This document is the agreement we build against.

---

## 2. User Story 001 — "Find a Tournament and See Our Club's Schedule" (Driving Scenario)

> "A tournament comes to mind — maybe the latest upcoming one. Let's say **Trick or Retreat**.
> I go to the app, type in 'Trick or Retreat', and it pulls up data from that tournament.
> It shows an event schedule with each of our fencers listed under it. I can see who is
> fencing at what time and on which day. Then I remember I also want to track James Smith —
> so I click 'track additional fencer' and track him too."

**Real-world anchor:** "Trick or Retreat ROC / RJCC" exists on AskFRED
(`/tournaments/f4fbfddf-8316-46d2-9392-8a8245059f86`) — Aug 22–23, NJ Convention & Exposition
Center, Edison NJ, ~20+ events (Vet / Junior / Cadet / Div IA / Div II, all three weapons).
USFA-managed. This is the tournament the flow must handle end-to-end.

### Flow

1. **Search:** User types a tournament name (e.g., "Trick or Retreat"). App searches
   **upcoming tournaments only** and returns a pickable list (name, dates, location).
   Search is backed by AskFRED (public `GET /tournaments?name=<query>`, confirmed working).
2. **Pick:** User selects the tournament from the results.
3. **Auto-match:** App attempts to match the selected AskFRED tournament to the same
   tournament on **FTL by name + dates** (FTL lookup requires the shared account session).
   If found, live data is available.
4. **Build schedule:** App fetches the tournament's events (from AskFRED and/or FTL),
   discovers club fencers per event (club name + abbreviations), and renders a
   **single-scroll, day-sectioned schedule**: day headers → events sorted by start time →
   each club fencer listed under the events they're in, with club affiliation shown and
   status/time where known.
5. **Track more:** User clicks "track additional fencer", searches the tournament for
   "James Smith", adds him. James appears **in the same event lists** as club fencers,
   with his **club affiliation** indicated so it's clear he's from another club.
6. **Refresh:** Manual refresh re-fetches live status (strip / pool / DE) from FTL.

### Edge cases locked in by this story

- Tournament exists on AskFRED but **not on FTL** → allow adding it; live data sections
  show a "live data unavailable" state (no error, no refusal).
- Multi-day tournaments → single scroll with day section headers (no tabs).
- A fencer is entered in multiple events → appears under each event.
- Same tournament name from different venues/years → upcoming-only search + result
  picker with dates/location to disambiguate.

### Acceptance criteria (Story 001)

- [ ] Typing a tournament name returns upcoming matches with name/date/location; picking
      one loads it.
- [ ] Club fencers (per configured club name + aliases) appear under their events, grouped
      by day, in start-time order.
- [ ] Each fencer entry shows the fencer's club (club members and added fencers alike).
- [ ] "Track additional fencer" search finds a fencer in the tournament and adds them to
      the same schedule lists.
- [ ] Manual refresh updates live status from FTL.

---

## 3. Current State of the Project (Baseline)

- **Stack (legacy):** Python 3, FastAPI, SQLAlchemy + SQLite, Jinja2, BeautifulSoup, requests,
  Pico CSS. Procfile + psycopg2 prepared for Heroku/Coolify deployment.
- **Features built (all complete):** FTL parsers (pool IDs, pool HTML, pool results JSON,
  DE tableau, tournament schedule, event rounds), resilient HTTP client with retry + TTL cache,
  auth system (register/login/sessions/CSRF), tournament setup (paste FTL URL, club + weapon
  filters), auto-discovery of club fencers, consolidated live dashboard grouped by status,
  manual fencer add/search, 48h TTL auto-archive, mobile-first card UI.
- **Test suite:** ~200 tests across `tests/ftl`, `tests/api`, `tests/web`.
- **Key docs:** `project-manifest.md`, `comms/plan.md`, `docs/ARCHITECTURE.md`,
  `docs/ftl-api-specification.md` (detailed FTL endpoint map, now partially obsolete).
- **Legacy data model:** User, UserSession, TrackedTournament, CachedEvent, TrackedFencer.

**Decision (from interview):** The app will be a **fresh rebuild**. The existing code is
reference material only — parsers, URL patterns, and research artifacts (`comms/ftl_research_*.md`)
are valuable, but we will not fix-in-place.

---

## 4. Goal 1 — Feasibility Investigation Findings (as of 2026-08-19)

Live probes were performed against all four sites. Summary matrix:

| Site | Site status | Access model now | Data accessibility | Blockers / notes |
|------|-------------|------------------|--------------------|------------------|
| **FencingTimeLive** | Up | **Login required for ALL tournament data** — every page (incl. homepage) 302-redirects to `/account/login` | Unknown — must verify behind a logged-in session | Login page states "Account creation is quick and free!" and contains a CSRF token (`<meta name="csrf_token">`). Old endpoints (`/pools/scores/...`, `/pools/results/data/...`, `/tableaus/scores/...`, `/tournaments/eventSchedule/...`) all redirect to login without a session. |
| **AskFRED** | Up (revamped platform, © 2023-2026 AskFRED Inc) | Public pages load with plain session cookies (Heroku-hosted, no Cloudflare) | Partially accessible | Tournament and results listing pages return 200. **URLs are now UUID-based** (e.g. `/tournaments/6d772f6a-8a3c-4502-a3a2-1aa20054bd15`) — old numeric-ID URLs/schemas are gone. Some paths (e.g. `/developers`) trigger a **reCAPTCHA "bot-challenge"** page ("We detected unusual traffic"). Old `/API/...` endpoints return 404. No official public API found; the `/developers` page (likely API docs) is gated behind the bot challenge. |
| **FencingTracker** | Up | Public, free, no auth | Accessible (archival) | Server-rendered pages (Django-style). `POST /search` with JSON body `{"query": ..., "limit": ...}` returns JSON fencer records (`usfa_id`, `name`, `club`). Fencer profiles at `/p/{usfa_id}/{name}`. Data is **archival** — "usually the day after" tournaments are published; US-focused. Old `api.fencingtracker.com` no longer resolves. |
| **USA Fencing** | Up | Public site (usafencing.org returns 200) | Unknown | `api.usafencing.org` does not resolve — no obvious public API subdomain. Membership/club roster/ratings data lives on the site; access method (public pages vs. developer program vs. member login) needs investigation. |

### Key takeaways

- **FTL is the only real-time source and is now gated behind a free account.** The feasibility
  question is: *does a logged-in session unlock the same endpoints and JSON/HTML schemas as
  before?* The old research artifacts describe the pre-login schema; we must diff them against
  what a session returns.
- **AskFRED is scrapable in part, with captcha risk.** Public listing pages work; some deep
  paths are gated by reCAPTCHA. Trigger conditions and rate limits need mapping.
- **FencingTracker is easily scrapable but not live.** It is a consumer of results, not a
  producer of real-time data — useful for history/ratings enrichment, not for live tracking.
- **USFA is the least explored** and needs a dedicated mini-investigation (club roster, ratings,
  membership data access).

---

## 5. Goal 2 — Confirmed Scope (from Interview)

### 5.1 Vision

> The primary function of the app is to **display the schedules of all fencers of our club at a
> tournament**, organized in a way that is useful to **coaches, parents, and teammates** who want
> to support the fencers.

The core question the app answers: **"Who from our club fences when, and what's their status
right now?"**

### 5.2 Confirmed decisions

| Topic | Decision |
|-------|----------|
| **Users / auth** | **Single user, no accounts.** No registration/login/passwords. (Frank is the only user; possibly his kids.) |
| **Freshness** | **Real-time is essential**, but updates are **manual refresh only** (no auto-polling for v1). |
| **Layout** | **Chronological ("by time")**: a timeline of *who fences when*, events ordered by start time, with each club fencer's bouts. |
| **Core features (v1)** | 1. **Fencer schedule cards** — each fencer's full schedule (events, pools, DE rounds, strips, times). 2. **Status timeline** — current status (fencing now / waiting / finished) and progression. 3. **Search by name** — look up any fencer in the tournament, not just club members. |
| **Manual tracking** | Ability to **add other fencers in a tournament to track** (non-club fencers) via a "track additional fencer" search. Added fencers appear in the **same event lists**, with their **club affiliation** indicated. |
| **Club identity** | Match on **club name + abbreviations** (e.g., "Elite Fencing Club" / "EFC"), configured by the user. |
| **Tournament entry** | **Search by name** (upcoming only), pick from results, app **auto-matches to FTL by name + dates** for live data. One tournament at a time. |
| **No FTL match** | Tournament can still be added; live sections show a "live data unavailable" state. |
| **Multi-day layout** | **Single scroll with day sections** (day headers), events sorted by start time within each day, club fencers listed under each event with club affiliation shown. |
| **Data retention** | **Auto-clean after the event** (like the legacy 48h TTL archive). No long-term history storage. |
| **Data sources** | **All four integrated from the start** — FTL (live schedule), AskFRED (tournament/results), FencingTracker (history), USFA (club roster & ratings). Exact v1 contribution of AskFRED/FencingTracker/USFA is **TBD / to be clarified**. |
| **Anti-bot posture** | **OK within reason** — work around reCAPTCHA challenges and behind-login scraping with polite requests, caching, and rate limits. |
| **FTL auth approach** | **One shared FTL account** — credentials in server config; app logs in programmatically and scrapes with the session. |
| **Codebase** | **Fresh rebuild** — new project structure; old code is reference only. |
| **Deployment** | **Local / self-hosted.** |
| **Stack** | No strong preference — pick something **extensible** for future features. (Recommendation below.) |

### 5.3 Out of scope for v1

- User accounts / auth / multi-tenancy
- Notifications (email/push alerts)
- Auto-refresh / polling
- Club roster auto-sync from USFA (manual club config instead)
- Long-term history / analytics dashboards
- Multi-tournament aggregation (one at a time)
- Weapon filter as a first-class concept (defer; club matching is the priority)

---

## 6. Proposed Architecture (Fresh Rebuild)

### 6.1 Recommended stack

- **Python 3 + FastAPI + SQLite (via SQLAlchemy) + Jinja2** — same family as the legacy app.
  Rationale: (a) familiar to the owner, (b) the legacy parsers and `comms/ftl_research_*.md`
  artifacts are directly reusable as reference, (c) FastAPI's structure scales well when features
  are added later. Alternative (if preferred): minimal stdlib server — but extensibility goal
  favors FastAPI.
- **BeautifulSoup** for HTML parsing (proven against FTL markup), **requests** (or httpx) for HTTP.
- Simple TTL in-memory cache (reuse the legacy `SimpleCache` pattern).
- Mobile-first, plain HTML/CSS (no JS framework needed for v1; timeline view is server-rendered).

### 6.2 Layered design

```
┌─────────────────────────────────────────────────────────────┐
│  UI (server-rendered Jinja2)                                │
│  - Tournament timeline (chronological, club fencers)        │
│  - Fencer schedule cards / status timeline                  │
│  - Search by name + add-to-track                            │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Service layer                                              │
│  - TournamentSearchService (search + pick + auto-match)     │
│  - TournamentMatcher (AskFRED ↔ FTL by name + dates)        │
│  - TournamentService (orchestration, status computation)    │
│  - ClubMatcher (name + abbreviation matching)               │
│  - TrackedFencerService (manual adds)                       │
│  - CleanupService (TTL / post-event purge)                  │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Source adapter layer  ←  KEY ARCHITECTURAL PIECE           │
│  Common interface per source:                               │
│    search_tournaments(query) → [TournamentMeta]             │
│    fetch_tournament(tournament_id) → TournamentMeta         │
│    fetch_events(tournament_id) → [Event]                    │
│    fetch_event_status(event_id) → EventStatus (pools/DE)    │
│    fetch_results(event_id) → [Placement]                    │
│    fetch_fencer(query) → [FencerProfile]                    │
│                                                             │
│  ├── FTLAdapter        (auth'd session: shared account)     │
│  ├── AskFREDAdapter    (UUID URLs, captcha-aware)           │
│  ├── FencingTrackerAdapter (POST /search, profile pages)    │
│  └── USAFencingAdapter (roster / ratings — method TBD)      │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  HTTP client layer (per-source session, retry, TTL cache,   │
│  rate limiting, captcha/challenge detection hooks)          │
└─────────────────────────────────────────────────────────────┘
```

**Why adapters:** the whole reason the project died is that sites changed their access model and
schemas. An adapter interface isolates each site's quirks (auth, URL scheme, JSON schema,
anti-bot behavior) behind a stable internal contract, so a single site changing again doesn't
break the app — it breaks one adapter.

### 6.3 Data model (v1, no users)

```
ClubConfig          — singleton config: club_name, aliases[] (abbreviations), ftl_credentials
Tournament          — id, source (askfred/...), external_id (AskFRED UUID), name, dates,
                      location, created_at, expires_at
FTLTournamentMatch — tournament_id FK, ftl_tournament_id, matched (bool), matched_at
                      (AskFRED → FTL name+date match result)
Event               — tournament_id FK, external_id, name, weapon, start_time, phase
                       (not_started | pools | de | complete)
PoolRound           — event_id FK, external_id (round id), pool list snapshot
Pool                — pool_round_id FK, pool_number, strip
Fencer              — external_id (per source), name, club, ratings (optional), usfa_id (optional)
TrackedFencer       — tournament_id FK, fencer_id FK, source ("club" | "manual")
FencerStatus        — event_id FK, fencer_id FK, phase, location (strip/pool/DE), result, updated_at
```

History is intentionally not retained: rows are purged when the tournament expires.

### 6.4 Configuration

Simple `config.yaml` (or `.env`):

```yaml
club:
  name: "My Fencing Club"
  aliases: ["MFC", "MYFC", "My Fencing Club"]
ftl:
  email: "..."
  password: "..."        # shared FTL account
askfred: {}              # optional
fencingtracker: {}       # optional
usafencing: {}           # optional
```

---

## 7. Feasibility Investigation Plan (Goal 1 — Detailed Steps)

This is the **first workstream** to execute after this spec is accepted. Each item ends with a
recorded finding in a `FEASIBILITY.md` (or per-site research notes like the legacy
`comms/ftl_research_*.md`).

### 7.1 FencingTimeLive (priority — the only live source)

1. **Create a free account** (Frank provides or creates one; credentials go in local config).
2. **Map the login flow:** GET `/account/login` (grab CSRF token + session cookie) → POST
   credentials → confirm session cookie grants access; check for captcha/2FA on login.
3. **Re-verify all legacy endpoints behind auth** with the new session, **plus the
   tournament search/lookup flow** needed by Story 001 (does FTL expose a tournament
   search by name? a list of upcoming tournaments? can we look up by name + date?):
   - `/tournaments/eventSchedule/{id}` (schedule page)
   - `/events/view/{id}` (event page, round discovery)
   - `/pools/scores/{event}/{round}` + `/{poolId}?dbut=true` (pool IDs + pool HTML)
   - `/pools/results/data/{event}/{round}` (results JSON)
   - `/tableaus/scores/{event}/{round}` + `/trees` + `/trees/{guid}/tables/...` (DE)
   - `/events/results/data/{event}` (final placements)
   - `/events/competitors/data/{event}` (competitors JSON — used for club discovery)
4. **Diff schemas** against the legacy artifacts (`docs/ftl-api-specification.md`,
   `comms/ftl_research_*.md`): same JSON fields? same CSS classes? new fields?
5. **Probe rate limits / abuse controls** on the authenticated session (how many requests before
   throttling/challenge).
6. **Test with a real upcoming tournament** (e.g., the old Capital Clash test tournament or a
   current one) to confirm end-to-end.
7. **Deliverable:** FTL feasibility verdict — *accessible behind login with same schema* /
   *schema changed (list diffs)* / *blocked (why)*, plus a working session-based fetch recipe.

### 7.2 AskFRED

1. Map which pages load without a challenge: `/tournaments`, `/results`, tournament detail
   (`/tournaments/{uuid}`), preregistrations, conversation.
2. Identify where the **bot-challenge triggers** (path, request pattern, IP vs. UA heuristics) —
   test with a clean session and repeated requests.
3. **Confirm the tournament search contract** used by Story 001: `GET /tournaments?name=<query>`
   (works today), result fields (name, dates, location, UUID), and the upcoming-only
   date filter (`date_by`).
4. Find JSON/data endpoints behind the listing pages (XHR calls in page JS) — tournament
   schedules, event times, final results per event.
4. Verify UUID-based URL scheme and whether old numeric-ID lookups still work.
5. Determine if `/developers` (API docs) is reachable with a real browser session / after
   solving captcha once.
6. **Deliverable:** AskFRED feasibility verdict + list of usable endpoints vs. gated ones.

### 7.3 FencingTracker

1. Confirm `POST /search` JSON endpoint contract (query, limit, fields).
2. Map fencer profile page (`/p/{usfa_id}/{name}`) — extract results, ratings, bout history;
   check for JSON endpoints used by `event-results.min.js`.
3. Check tournament/event results pages and any club pages.
4. Probe rate limits and ToS posture (site says "Free since 2020" — likely lenient, but confirm
   expected request volume).
5. **Deliverable:** FencingTracker feasibility verdict + endpoint map for history enrichment.

### 7.4 USA Fencing (usafencing.org)

1. Determine how club rosters / membership are exposed: public pages, member portal login, or a
   developer/API program (research their developer resources).
2. Check whether ratings are obtainable publicly (they publish rating lists).
3. Note authentication requirements and rate limits.
4. **Deliverable:** USFA feasibility verdict + access method recommendation (may require a USFA
   account; Frank to advise).

### 7.5 Feasibility matrix output

One table: **source × data need × accessible? × method × auth needed × risk × notes**, appended
to this spec or `docs/FEASIBILITY.md`.

---

## 8. Rebuild Milestones (Goal 2 — after feasibility)

| Milestone | Scope | Exit criteria |
|-----------|-------|---------------|
| **M0 — Feasibility** | Section 6 work | Feasibility matrix complete; FTL session-based fetch proven |
| **M1 — Scaffold** | New project skeleton (stack decision finalized), config loading, DB models, HTTP client layer with retry/cache | App boots locally; config-driven club identity |
| **M2 — FTL adapter** | Login/session handling + tournament → events → pools/DE → status/results pipeline | A real tournament produces structured data offline-tested against fixtures |
| **M2b — AskFRED search** | `search_tournaments(query)` (upcoming only) + tournament detail (events, dates, location) | Searching "Trick or Retreat" returns the real ROC/RJCC tournament |
| **M2c — Matcher** | AskFRED → FTL auto-match by name + dates; "live unavailable" fallback state | Matching succeeds for a real tournament; gracefully degrades when unmatched |
| **M3 — Core UI** | Search page, single-scroll day-section schedule (events → club fencers with club shown), status computation, track-additional-fencer search, manual refresh | Frank can search "Trick or Retreat", see the club's full day at a glance, and add James Smith |
| **M4 — Cleanup** | Post-event purge (TTL) | Old tournaments disappear automatically |
| **M5 — Other sources** | AskFRED / FencingTracker / USFA adapters wired per feasibility findings | Each adapter produces data or is explicitly deferred with rationale |

---

## 9. Success Criteria

- [ ] Feasibility matrix answers "can we still access these sites?" with evidence (not guesses)
- [ ] FTL access proven behind a shared free account (session-based)
- [ ] Search a tournament by name (upcoming only) → pick it → app shows a single-scroll,
      day-sectioned schedule of all club fencers under their events, with current status
      (fencing now / waiting / finished) via manual refresh
- [ ] Story 001 acceptance criteria (§2) all pass end-to-end, including adding James Smith
      and seeing his club affiliation in the same lists
- [ ] No accounts/passwords; runs locally; data auto-cleaned after the event
- [ ] Adapter layer in place so a future source change breaks one adapter, not the app

---

## 10. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| FTL login adds captcha/2FA or device fingerprinting | Medium | Research login flow early (M0); test from the deployment host; fall back to manual session-cookie injection |
| FTL schemas changed behind login (not just access) | Medium | Diff against legacy artifacts in M0; update parsers; keep fixtures-based tests |
| AskFRED → FTL tournament matching unreliable | Medium | Match on name + dates with fuzzy/date-window tolerance; manual re-link fallback if auto-match fails |
| AskFRED bot-challenge blocks needed endpoints | Medium | Map trigger conditions; polite rates + caching; prefer non-gated endpoints; document manual-verification fallback |
| Scraping ToS changes (any site) | Low-Medium | Research ToS per site in M0; keep request volume low; no reselling of data |
| USFA data requires membership credentials | Medium | Investigate in M0; Frank to decide whether to provide credentials or drop that source |
| Another schema change mid-build | Always possible | Adapter isolation + fixture tests per source |

---

## 11. Open Questions (to resolve next)

1. **FTL tournament discovery behind login** — does FTL expose a tournament search / upcoming
   list that we can use for AskFRED → FTL matching, or must we match by name + dates against
   known FTL tournament URLs? (Answered during M0 feasibility.)
2. **AskFRED / FencingTracker / USFA v1 roles** — beyond Story 001 (AskFRED = tournament search
   + schedule), Frank said the rest "will need further clarification later." Proposed default:
   FTL feeds live status; AskFRED supplies event times/results; FencingTracker supplies bout
   history on fencer cards; USFA supplies club roster/ratings **if** accessible. Confirm or adjust.
3. **USFA access method** — does Frank have (or can he get) a USFA account/credentials, and is
   he OK with the app using them?
4. **FTL account creation** — Frank to create/provide the shared FTL test account for M0.
5. **Stack confirmation** — approve the recommended Python/FastAPI/SQLite stack or pick another.
6. **Club config editing** — plain config file OK, or a small settings page in the app?
7. **What "who is fencing at what time" means per fencer** — event start time only for v1, or
   per-fencer bout times (pools/DE round start times) when FTL provides them?

---

## 12. Reference Materials

- Legacy manifest / plan: `project-manifest.md`, `comms/plan.md`, `comms/NEXT_STEPS.md`
- FTL endpoint spec (partially obsolete, still the best schema reference): `docs/ftl-api-specification.md`
- FTL research artifacts: `comms/ftl_research*.md`
- Legacy FTL client: `app/ftl/client.py`, `app/ftl/parsers/`
- Test event (legacy): Capital Clash — `BBA4B7FACC464C93BA534ACE381A6C46`; November NAC 2025
  Div I Men's Épée — `54B9EF9A9707492E93F1D1F46CF715A2`

---

*End of spec. Next step: resolve the open questions in §10, then execute M0 (feasibility).*
