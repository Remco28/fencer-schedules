# Next Steps for Fencer Schedules

**Last Updated:** 2025-11-26
**Current Phase:** Phase 2 Implementation (in progress)

---

## Immediate Tasks (Week 1)

### Done
- ✅ Day 1: FTL scaffold + pool ID extractor (`app/ftl/parsers/pool_ids.py`, tests in `tests/ftl/test_pool_ids.py`)
- ✅ Day 2: Pool HTML parser (strip/fencers/bouts) (`app/ftl/parsers/pools.py`, tests in `tests/ftl/test_pools_parser.py`)
- ✅ Sample artifacts saved: `comms/ftl_research_human_pool_ids.md`, `comms/ftl_research_human_pools.md`

---

### Day 1: Setup & Pool ID Extraction
- [x] Read `docs/ftl-api-specification.md` (complete technical spec)
- [x] Set up Python project structure (`app/ftl/`, `app/database.py` at repo root)
- [x] Install scraper dependencies: `requests`, `beautifulsoup4`, `pytest`
- [x] Implement pool ID extractor (parse JavaScript array from HTML)
- [x] Write unit tests using saved HTML samples in `comms/ftl_research_human_pool_ids.md`
- [ ] Test against live FTL data (November NAC event) — **TO DO** (manual)

### Day 2-3: Pool HTML Parser
- [x] Implement pool HTML parser (extract strip, fencers, bout results)
- [x] Handle edge cases (missing strip assignment, incomplete pools)
- [x] Write unit tests using `comms/ftl_research_human_pools.md`
- [ ] Test with all 45 pools from test event — **TO DO** (after bulk fetching)

### Day 4: Pool Results JSON Parser
- [ ] Implement pool results JSON parser (advancement status)
- [ ] Extract fencer data, club, place, advanced/eliminated status
- [ ] Write unit tests using `comms/ftl_research_human_pools_results.md`
- [ ] Verify advancement indicator logic

### Day 5-7: DE Tableau Parser (Basic)
- [ ] Implement basic tableau parser (find tracked fencers in bracket)
- [ ] Extract match results, strip assignments, elimination status
- [ ] Write unit tests using `comms/ftl_research_human.md`
- [ ] Integration test: Full event data extraction (pools + DEs)

## Week 2 Tasks

### HTTP Client & Parallel Fetching
- [ ] Build HTTP client with rate limiting (max 10 concurrent) — reuse `requests`; consider `httpx` if async later
- [ ] Implement parallel pool fetching (ThreadPoolExecutor)
- [ ] Add timeout handling (10 sec per request)
- [ ] Add retry logic (3 attempts with exponential backoff)
- [ ] Test performance (should be ~2 seconds for 45 pools)

### Caching Layer
- [ ] Implement in-memory cache (development)
- [ ] Add cache invalidation logic (3-min TTL for active pools)
- [ ] Test cache hit/miss behavior
- [ ] Plan Redis integration (production - future)

### Basic API Endpoints
- [ ] Set up FastAPI or Flask
- [ ] Create endpoint: `GET /api/pools/{eventId}/{roundId}` (returns all pools)
- [ ] Create endpoint: `GET /api/pools/{eventId}/{roundId}/fencer/{name}` (find specific fencer)
- [ ] Create endpoint: `GET /api/de/{eventId}/{roundId}` (DE bracket)
- [ ] Add request validation and error handling
- [ ] Write API documentation (OpenAPI/Swagger)

## Week 3 Tasks (Frontend - Phase 1 Integration)

### Mobile-First UI
- [ ] Decide on frontend framework (React, Vue, or server-rendered HTML)
- [ ] Create fencer search page
- [ ] Create pool strip display page ("Where is my fencer?")
- [ ] Create advancement status page ("Who made the cut?")
- [ ] Add loading states and error handling
- [ ] Implement auto-refresh during active competition (optional)

## Week 4 Tasks (Testing & Polish)

### Live Tournament Testing
- [ ] Identify upcoming tournament for testing
- [ ] Deploy to staging environment
- [ ] Test with real coaches during live event
- [ ] Gather feedback on UX and performance
- [ ] Fix critical bugs discovered in production
- [ ] Iterate on UI based on feedback

### Documentation & Deployment
- [ ] Write deployment guide
- [ ] Set up production environment (Heroku, Railway, or DigitalOcean)
- [ ] Configure monitoring and alerting
- [ ] Add user-facing documentation
- [ ] Plan Phase 1 integration (user auth, fencer tracking)

## Phase 1 Tasks (Parallel or Sequential)

### Core Schedule MVP (Non-Live Features)
- [ ] User authentication (registration, login)
- [ ] User profile (set home club)
- [ ] Fencer search and tracking (add/remove fencers to watchlist)
- [ ] Tournament listing (from `fencingtracker.com`)
- [ ] Static schedule view (show tracked fencers in tournament)

**Note:** Phase 1 can be developed in parallel with Phase 2, or Phase 2 can be completed first as a standalone tool.

## Future Enhancements (Post-MVP)

### Advanced Features
- [ ] Automatic event matching (find FTL URLs automatically)
- [ ] WebSocket real-time updates (instead of polling)
- [ ] Push notifications for strip assignments
- [ ] Historical data tracking (save tournament results)
- [ ] Coach dashboard (multiple fencers at once)
- [ ] Club leaderboard (how did our club do overall?)

### Infrastructure Improvements
- [ ] Redis caching (production)
- [ ] Rate limiting middleware
- [ ] Comprehensive monitoring (Sentry, DataDog)
- [ ] Automated testing pipeline (CI/CD)
- [ ] Performance profiling and optimization

---

## Completed Tasks

- [x] Define the project (see `comms/plan.md`)
- [x] Create an implementation roadmap (see `comms/plan.md`)
- [x] Research FencingTimeLive scraping feasibility ✅ **2025-11-20**
- [x] Document FTL API endpoints and data structures ✅ **2025-11-20**
- [x] Create technical specification (`docs/ftl-api-specification.md`) ✅ **2025-11-20**
- [x] Assess risks and mitigation strategies ✅ **2025-11-20**
- [x] Collect sample data for testing ✅ **2025-11-20**

---

## Priority Legend

🔥 **Critical** - Blocks other work
⚡ **High** - Needed for MVP
📊 **Medium** - Important but not blocking
💡 **Low** - Nice to have

**Current Priority:** 🔥 Week 1 tasks (scraper parsers)

---

Notes:
- This file tracks the technical implementation roadmap
- See `comms/plan.md` for overall project phases
- See `docs/ftl-api-specification.md` for detailed implementation guide
- Update checkboxes as tasks are completed
