# FTL Tournament Discovery Research Summary

**Date:** 2026-01-15
**Status:** COMPLETE - Ready for Implementation

## Executive Summary

Research confirms that tournament-level discovery is **feasible** using FencingTimeLive's existing HTML structure. All required data can be extracted via server-side scraping without JavaScript execution.

## Key Findings

### 1. Tournament Schedule Page

**URL:** `/tournaments/eventSchedule/{tournament_id}`

**Extracts:**
- Event list with IDs, names, dates, times
- Weapon type (from event name)
- Status (finished, in progress, not started)

**Parsing:** BeautifulSoup on server-rendered HTML tables.

### 2. Event Page → Round Discovery

**URL:** `/events/view/{event_id}` (redirects to `/events/results/{event_id}`)

**Extracts:**
- Pool round ID from `/pools/scores/{event_id}/{pool_round_id}` link
- DE round ID from `/tableaus/scores/{event_id}/{de_round_id}` link

**Parsing:** Regex on navigation link hrefs.

### 3. Competitors JSON Endpoint

**URL:** `/events/competitors/data/{event_id}`

**Extracts:**
- All fencers with full club information
- Primary and secondary club names
- Name, division, country, rating

**Parsing:** Direct JSON response - no HTML parsing needed.

**This is the key endpoint for club-based filtering.**

## Data Flow for New Feature

```
1. User enters tournament URL
   └── Extract tournament_id from URL

2. Fetch tournament schedule page
   └── Parse event list (id, name, date, time, weapon)

3. For each event matching weapon filter:
   a. Fetch event page
      └── Extract pool_round_id, de_round_id from nav links

   b. Fetch competitors JSON
      └── Filter fencers by club name
      └── Build tracked fencer list

4. For tracked events with active fencers:
   └── Use existing parsers (pools, results, DE tableau)
   └── Aggregate fencer status across events

5. Render consolidated dashboard
```

## URL Pattern Summary

| Purpose | URL Pattern |
|---------|-------------|
| Tournament schedule | `/tournaments/eventSchedule/{tournament_id}` |
| Event page | `/events/view/{event_id}` |
| Competitors JSON | `/events/competitors/data/{event_id}` |
| Pool scores | `/pools/scores/{event_id}/{pool_round_id}` |
| Pool results JSON | `/pools/results/data/{event_id}/{pool_round_id}` |
| DE tableau | `/tableaus/scores/{event_id}/{de_round_id}` |

## Reusable Existing Code

| Component | Reuse Level | Notes |
|-----------|-------------|-------|
| `parsers/pool_ids.py` | 100% | Pool ID extraction unchanged |
| `parsers/pools.py` | 100% | Pool HTML parsing unchanged |
| `parsers/pool_results.py` | 100% | Results JSON parsing unchanged |
| `parsers/de_tableau.py` | 100% | DE parsing unchanged |
| `client.py` | 100% | HTTP client with cache unchanged |

## New Parsers Needed

| Parser | Complexity | Input | Output |
|--------|------------|-------|--------|
| `tournament_schedule.py` | Low | HTML | List of events |
| `event_rounds.py` | Low | HTML | pool_round_id, de_round_id |
| (None for competitors) | - | JSON | Direct use |

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| HTML structure changes | Low | FTL structure stable; use defensive parsing |
| Rate limiting | Low | Existing cache + parallel fetch handles this |
| Events without pools | Low | Check for link presence before parsing |
| Club name variations | Medium | Use substring matching; consider user confirmation |

## Sample Test Data

- **Tournament:** Junior Olympics
- **Tournament ID:** `BBA4B7FACC464C93BA534ACE381A6C46`
- **Sample Event:** Junior Women's Saber
- **Event ID:** `7A76D82961504CC7A885D0E0E60D60C3`
- **Pool Round ID:** `5610A0F90E36406CA634B86053BCD6D8`
- **DE Round ID:** `BC0A8665F5CD45DE9DA9024724076EAC`

## Research Artifacts

- `comms/ftl_research_tournament_schedule.md` - Schedule page HTML structure
- `comms/ftl_research_event_page.md` - Event page round discovery
- `comms/ftl_research_competitors_json.md` - Competitors JSON format

## Verdict

**GO FOR IMPLEMENTATION**

All required data is accessible. Estimated new code: ~200 lines for two new parsers. Existing infrastructure handles 90% of the work.

## Next Steps

1. **Phase B:** Add `club` field to User model
2. **Phase C:** Implement tournament schedule parser + event round discovery
3. **Phase D:** Build orchestration layer and dashboard UI
