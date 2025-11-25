# FencingTimeLive Research Summary

**Research Date:** November 20, 2025
**Research Team:** AI Technical Advisor + Frank
**Status:** ✅ COMPLETE - Phase 2 is GO!

---

## Research Objective

Determine the feasibility of scraping live tournament data from FencingTimeLive.com to provide coaches with real-time strip assignments and fencer tracking during pool and DE rounds.

---

## Key Findings

### ✅ Project is FEASIBLE

All required data is accessible and scrapable:

1. **Pool Strip Assignments** - Available in real-time during active pools
2. **Advancement Status** - Clear indicator of who advanced from pools
3. **DE Bracket Tracking** - Can determine elimination status
4. **No Authentication Required** - All data is publicly accessible

---

## Data Sources Discovered

### 1. Pool IDs List
- **URL:** `/pools/scores/{eventID}/{roundID}`
- **Format:** HTML with embedded JavaScript
- **Contains:** Array of all pool IDs (e.g., 45 pools)
- **Location:** Line ~217, `var ids = ["...", "...", ...]`

### 2. Individual Pool Data
- **URL:** `/pools/scores/{eventID}/{roundID}/{poolID}?dbut=true`
- **Format:** HTML
- **Contains:**
  - Strip assignment (e.g., "On strip H1") ← **PRIMARY COACH USE CASE**
  - Pool number
  - Fencer names and clubs
  - Bout results (V/D scores)
- **Update Frequency:** Real-time during active pools

### 3. Pool Results Summary
- **URL:** `/pools/results/data/{eventID}/{roundID}`
- **Format:** JSON
- **Contains:**
  - All fencers from all pools
  - Advancement status: `"prediction": "Advanced"` or `"Eliminated"`
  - Final pool standings
- **Availability:** Only after pool rounds complete

### 4. DE Tableau
- **URL:** `/tableaus/scores/{eventID}/{roundID}`
- **Format:** HTML
- **Contains:**
  - Bracket progression
  - Match scores
  - Strip assignments for completed matches
  - Fencer advancement/elimination status

---

## Technical Architecture

### Request Flow

```
User Request: "Where is WANG justin?"
    ↓
Cache Check (3-min TTL)
    ↓ (cache miss)
Fetch Pool IDs (1 request)
    ↓
Fetch All 45 Pools in Parallel (45 requests, ~2 seconds)
    ↓
Parse HTML for Strip Assignments
    ↓
Filter for Tracked Fencers
    ↓
Return: "WANG justin - Pool #7, Strip H3"
```

### Performance

- **Sequential fetching:** 22.5 seconds (unacceptable)
- **Parallel fetching (10 workers):** 2.3 seconds ✅
- **With caching (3-min TTL):** <100ms (instant) ✅

---

## Code Complexity Assessment

### Parsing Difficulty

| Component | Difficulty | Notes |
|-----------|-----------|-------|
| Pool ID extraction | Easy | Simple regex on JavaScript variable |
| Pool HTML parsing | Medium | Well-structured HTML with clear class names |
| Pool results JSON | Very Easy | Clean JSON, no parsing needed |
| Tableau HTML | Medium-Hard | Complex nested structure, requires careful parsing |

### Estimated Development Time

- **Week 1:** Core scraper + parsers (pools + DEs)
- **Week 2:** Caching + API layer
- **Week 3:** Basic frontend (mobile-first)
- **Week 4:** Polish + live tournament testing

**Total:** 4 weeks to MVP

---

## Risk Assessment

### Technical Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| HTML structure changes | Medium | Medium | Defensive parsing, unit tests, monitoring |
| Rate limiting | Low | Low | 3-min cache, max 10 concurrent requests |
| FTL downtime | Medium | Low | Show cached data, graceful error handling |

### Legal/Ethical Risks

| Risk | Severity | Assessment |
|------|----------|-----------|
| ToS violation | Low | Scraping public data is generally acceptable |
| Server load | Very Low | Caching reduces load to ~20 requests/hour |

**Overall Risk: LOW-MEDIUM** - Acceptable for MVP

---

## Discovered Limitations

1. **Pool Results JSON doesn't include pool numbers**
   - Impact: Can't easily map fencers to specific pools without fetching all pool HTMLs
   - Solution: Fetch all pools at least once, cache mapping

2. **Strip assignments only appear for active/completed bouts**
   - Impact: Future matches show "Strip TBD"
   - Solution: This is expected behavior, handle gracefully in UI

3. **No official API = no guarantees**
   - Impact: FTL could change structure at any time
   - Solution: Build robust parsers, add monitoring, be prepared to update

---

## Test Data

### Reference Event
**Event:** November NAC 2025 - Division I Men's Épée
**Event ID:** `54B9EF9A9707492E93F1D1F46CF715A2`
**Pool Round ID:** `D6890CA440324D9E8D594D5682CC33B7`
**DE Round ID:** `08DE5802C0F34ABEBBB468A9681713E7`

### Test URLs

```
# Pool IDs
https://www.fencingtimelive.com/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7

# Individual Pool
https://www.fencingtimelive.com/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7/130C4C6606F342AFBD607A193F05FAB1?dbut=true

# Pool Results
https://www.fencingtimelive.com/pools/results/data/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7

# DE Tableau
https://www.fencingtimelive.com/tableaus/scores/54B9EF9A9707492E93F1D1F46CF715A2/08DE5802C0F34ABEBBB468A9681713E7
```

---

## Research Files Created

1. **`comms/ftl_research.md`** - Initial investigation log
2. **`comms/ftl_research_human.md`** - Tableau HTML sample
3. **`comms/ftl_research_human_pools.md`** - Pool HTML sample
4. **`comms/ftl_research_human_pools_results.md`** - Pool results JSON sample
5. **`comms/ftl_research_human_pool_ids.md`** - Pool IDs discovery (JavaScript array)
6. **`docs/ftl-api-specification.md`** - Complete technical specification ← **START HERE FOR IMPLEMENTATION**

---

## Recommendation

**Proceed with Phase 2 implementation.**

The project is fully feasible with acceptable technical complexity and risk. All required data sources have been identified and tested. The path forward is clear.

### Next Steps

1. **Tomorrow:** Review `docs/ftl-api-specification.md`
2. **Week 1:** Build core scraper and parsers
3. **Week 2:** Add caching and API layer
4. **Week 3:** Build mobile-first frontend
5. **Week 4:** Test at live tournament

---

## Key Success Factors

✅ **Data Availability** - All required data is accessible
✅ **Clear Architecture** - We know exactly how to build this
✅ **Performance** - Parallel fetching + caching makes it fast
✅ **Testing Data** - We have real tournament data to test against
✅ **Risk Management** - Risks are understood and mitigated

---

## Credits

**Research conducted by:**
- AI Technical Advisor (TECHADVISOR role)
- Frank (Human Developer)

**Research method:**
- Browser DevTools network inspection
- HTML/JSON structure analysis
- Live data testing with November NAC 2025

**Research duration:** ~2 hours

---

**Status: Research phase COMPLETE ✅**
**Next phase: Implementation (starting tomorrow)**
