# FencingTimeLive (FTL) API Specification & Implementation Guide

**Version:** 1.0
**Date:** 2025-11-20
**Status:** Research Complete - Ready for Implementation

---

## Executive Summary

This document provides a complete technical specification for scraping live fencing tournament data from FencingTimeLive.com. All required data sources have been identified, tested, and documented.

**Key Findings:**
- ✅ All data is accessible via HTTP requests (no authentication required for public events)
- ✅ Pool strip assignments are available in real-time during active competition
- ✅ Advancement status (who made the cut) is clearly indicated
- ✅ DE bracket progression is trackable
- ✅ No public API exists; all data must be scraped from HTML or internal JSON endpoints

**Feasibility:** **HIGH** - Project is fully feasible with acceptable complexity and risk.

---

## Table of Contents

1. [Data Sources Overview](#data-sources-overview)
2. [Endpoint Specifications](#endpoint-specifications)
3. [Data Structures](#data-structures)
4. [Implementation Architecture](#implementation-architecture)
5. [Parsing Strategies](#parsing-strategies)
6. [Caching & Performance](#caching--performance)
7. [Risk Assessment](#risk-assessment)
8. [Code Examples](#code-examples)
9. [Testing Data](#testing-data)

---

## Data Sources Overview

### URL Structure Pattern

All FTL URLs follow this pattern:
```
https://www.fencingtimelive.com/{resource}/{action}/{eventID}/{roundID}/{itemID}
```

**Common IDs:**
- `eventID`: 32-character hex (e.g., `54B9EF9A9707492E93F1D1F46CF715A2`)
- `roundID`: 32-character hex (e.g., `D6890CA440324D9E8D594D5682CC33B7`)
- `poolID`: 32-character hex (e.g., `130C4C6606F342AFBD607A193F05FAB1`)

### Four Core Data Sources

| Data Source | Use Case | Format | Real-time? |
|------------|----------|---------|------------|
| Pool IDs List | Discover all pools in event | HTML (embedded JS) | No |
| Individual Pool Data | Strip assignments during pools | HTML | Yes |
| Pool Results Summary | Who advanced after pools | JSON | No |
| DE Tableau | Elimination bracket tracking | HTML | Yes |

---

## Endpoint Specifications

### 1. Pool IDs Discovery

**Endpoint:**
```
GET /pools/scores/{eventID}/{roundID}
```

**Response Type:** HTML with embedded JavaScript

**Purpose:** Get list of all pool IDs for an event

**Key Data Location:**
```javascript
// Found at line ~217 in HTML response
var ids = [
    "130C4C6606F342AFBD607A193F05FAB1",
    "BAB54F30F50544188F2EA794B021A72B",
    // ... 43 more pool IDs
];
```

**Extraction Method:**
- Parse HTML
- Locate `<script>` tag containing `var ids = `
- Extract array using regex: `var ids = \[(.*?)\];`
- Split by comma and clean quotes

**Example:**
```
URL: https://www.fencingtimelive.com/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7
Returns: HTML page with 45 pool IDs in JavaScript array
```

---

### 2. Individual Pool Data (Strip Assignments)

**Endpoint:**
```
GET /pools/scores/{eventID}/{roundID}/{poolID}?dbut=true
```

**Response Type:** HTML fragment

**Purpose:** Get real-time strip assignment and bout results for a single pool

**Key HTML Elements:**

```html
<!-- Pool Number -->
<h4 class="poolNum">Pool #1</h4>

<!-- Strip Assignment (THIS IS THE PRIMARY USE CASE) -->
<span class="poolStripTime">
    On strip H1
</span>

<!-- Fencer Name -->
<span class="poolCompName">WANG justin</span>

<!-- Club Affiliation -->
<span class="poolAffil">CFC / New England / USA</span>

<!-- Pool Position -->
<td class="poolPos">1</td>

<!-- Bout Results -->
<td class="poolScore poolScoreV">
    <span>V5</span>  <!-- Victory, 5 touches -->
</td>
<td class="poolScore poolScoreD">
    <span>D3</span>  <!-- Defeat, 3 touches -->
</td>

<!-- Final Statistics -->
<td class="poolResult">6</td>      <!-- Victories -->
<td class="poolResult">1.00</td>   <!-- V/M ratio -->
<td class="poolResult">27</td>     <!-- Touches Scored -->
<td class="poolResult">13</td>     <!-- Touches Received -->
<td class="poolResult">+14</td>    <!-- Indicator -->
```

**Update Frequency:** Real-time during active pools

**Example:**
```
URL: https://www.fencingtimelive.com/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7/130C4C6606F342AFBD607A193F05FAB1?dbut=true
Returns: HTML showing Pool #1 fencers on Strip H1
```

---

### 3. Pool Results Summary (Advancement Status)

**Endpoint:**
```
GET /pools/results/data/{eventID}/{roundID}
```

**Response Type:** JSON

**Purpose:** Get complete pool results with advancement predictions

**Availability:** Only after pool rounds are complete

**JSON Structure:**
```json
[
  {
    "id": "425B00719E2740C18ECEC299142D3CF3",
    "v": 6,                              // Victories
    "m": 6,                              // Matches
    "vm": 1.0,                           // Victory/Match ratio
    "ts": 30,                            // Touches Scored
    "tr": 9,                             // Touches Received
    "ind": 21,                           // Indicator (+/-)
    "prediction": "Advanced",            // ← KEY: Advancement status
    "name": "IMREK Elijah S.",
    "div": "Gulf Coast",
    "country": "USA",
    "club1": "University Of Notre Dame NCAA",
    "club2": "Alliance Fencing Academy",
    "search": "imrek elijah s.|gulf coast|usa|...",
    "place": 1,                          // Final placement
    "tie": false
  },
  // ... array continues for all fencers
]
```

**Key Field:** `prediction`
- `"Advanced"` = Fencer made the cut, will fence DEs
- Other values (presumably `"Eliminated"`) = Did not advance

**Example:**
```
URL: https://www.fencingtimelive.com/pools/results/data/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7
Returns: JSON array with all fencers sorted by placement
```

---

### 4. DE Tableau (Elimination Bracket)

**Endpoint:**
```
GET /tableaus/scores/{eventID}/{roundID}
```

**Response Type:** HTML

**Purpose:** Track fencer progression through elimination bracket

**Key HTML Elements:**

```html
<!-- Fencer Last Name -->
<span class='tcln'>WANG</span>

<!-- Fencer First Name -->
<span class='tcfn'>justin</span>

<!-- Seed Position -->
<span class='tseed'>(45)&nbsp;</span>

<!-- Club/Division -->
<span class='tcaff'>
    <br/>
    CFC / New England / <span class='flag flagUSA'></span>
    USA
</span>

<!-- Match Score (completed) -->
<span class='tsco'>
    15 - 9<br/>
    <span class='tref'>
        Ref SMITH John / Texas / USA
    </span>
    <br/>
    <span class='tref'>11:31 AM &#160;Strip L1</span>  <!-- Strip assignment -->
    &nbsp;
</span>

<!-- Match Not Yet Started (future) -->
<span class='tsco'>&nbsp;</span>  <!-- Empty = match hasn't happened -->
```

**Determining Elimination Status:**
1. Find fencer in bracket
2. Check their most recent match (rightmost column they appear in)
3. If match has score AND they appear in next round → Still active
4. If match has score AND they DON'T appear in next round → Eliminated
5. If match score is empty (`&nbsp;`) → Upcoming match

**CSS Classes:**
- `tcln` = Last name
- `tcfn` = First name
- `tseed` = Seed position
- `tcaff` = Affiliation (club/country)
- `tsco` = Score container
- `tref` = Referee/strip/time info

**Example:**
```
URL: https://www.fencingtimelive.com/tableaus/scores/54B9EF9A9707492E93F1D1F46CF715A2/08DE5802C0F34ABEBBB468A9681713E7
Returns: HTML showing DE bracket with all matches
```

---

## Data Structures

### Fencer Object (Internal Data Model)

```typescript
interface Fencer {
  id: string;              // FTL fencer ID
  lastName: string;
  firstName: string;
  fullName: string;        // "WANG justin"
  club: string;            // Primary club
  club2?: string;          // Secondary club (optional)
  division?: string;       // Geographic division
  country: string;         // Country code (USA, CAN, etc.)
}
```

### Pool Assignment

```typescript
interface PoolAssignment {
  fencer: Fencer;
  poolNumber: number;      // 1-45
  poolId: string;          // UUID from FTL
  strip: string | null;    // "H1", "A3", etc. or null if not assigned yet
  position: number;        // Position within pool (1-7 typically)

  // Bout results
  victories: number;
  defeats: number;
  vmRatio: number;
  touchesScored: number;
  touchesReceived: number;
  indicator: number;       // TS - TR

  // Status
  complete: boolean;       // All bouts finished?

  // Timestamp
  lastUpdated: Date;
}
```

### Pool Results

```typescript
interface PoolResult {
  fencer: Fencer;
  place: number;           // Overall placement after pools
  indicator: number;
  victories: number;
  vmRatio: number;
  advanced: boolean;       // Derived from prediction === "Advanced"
  tie: boolean;
}
```

### DE Match

```typescript
interface DEMatch {
  fencer: Fencer;
  opponent?: Fencer;       // null if BYE or future match
  score?: {
    fencerScore: number;
    opponentScore: number;
  };
  strip?: string;          // "L1", "T1", etc.
  time?: string;           // "11:31 AM"
  referee?: string;
  round: string;           // "Table of 64", "Table of 32", etc.
  status: 'completed' | 'upcoming' | 'in_progress';
  won?: boolean;           // Only for completed matches
}
```

### Complete Event State

```typescript
interface EventState {
  eventId: string;
  eventName: string;        // "Div I Men's Épée"
  tournamentName: string;   // "November NAC"
  date: Date;

  // Pool round data
  poolRoundId: string;
  poolsComplete: boolean;
  poolAssignments: PoolAssignment[];
  poolResults?: PoolResult[];  // Only available after pools complete

  // DE round data
  deRoundId: string;
  deMatches: DEMatch[];

  // Cache metadata
  lastFetched: Date;
  cacheExpiry: Date;
}
```

---

## Implementation Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    User Request                              │
│         "Where is WANG justin fencing?"                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Cache Layer                                 │
│  Check if data exists and is fresh (< 3 min old)            │
└────────────┬────────────────────────────┬───────────────────┘
             │ Cache HIT                  │ Cache MISS
             ▼                            ▼
    ┌────────────────┐         ┌──────────────────────────────┐
    │ Return cached  │         │    FTL Scraper Service       │
    │     data       │         └──────────┬───────────────────┘
    └────────────────┘                    │
                                          ▼
                              ┌───────────────────────────────┐
                              │  Determine Event Phase        │
                              │  - Pools active?              │
                              │  - Pools complete?            │
                              │  - DEs active?                │
                              └───────┬───────────────────────┘
                                      │
                   ┌──────────────────┼──────────────────┐
                   ▼                  ▼                  ▼
         ┌─────────────────┐ ┌─────────────┐  ┌────────────────┐
         │  Fetch Pool IDs │ │Fetch Pool   │  │  Fetch DE      │
         │  (1 request)    │ │Results JSON │  │  Tableau HTML  │
         └────────┬────────┘ │(1 request)  │  │  (1 request)   │
                  │          └──────┬──────┘  └───────┬────────┘
                  ▼                 │                 │
         ┌─────────────────┐       │                 │
         │ Fetch 45 Pools  │       │                 │
         │  in Parallel    │       │                 │
         │  (45 requests)  │       │                 │
         └────────┬────────┘       │                 │
                  │                │                 │
                  ▼                ▼                 ▼
         ┌────────────────────────────────────────────────────┐
         │           Parse HTML/JSON                          │
         │           Extract Fencer Data                       │
         └────────────────────┬───────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────────────────────┐
         │         Filter for Tracked Fencers                 │
         │         Build Response Object                       │
         └────────────────────┬───────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────────────────────┐
         │         Update Cache (3-5 min TTL)                 │
         └────────────────────┬───────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────────────────────┐
         │         Return to User                              │
         │  "WANG justin - Pool #7, Strip H3"                 │
         └────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. HTTP Client Layer
- Handles all requests to FTL
- Implements rate limiting (max 10 concurrent requests)
- Adds appropriate headers (User-Agent, etc.)
- Handles retries on failure
- Times out after 10 seconds per request

#### 2. Parser Layer
- **PoolIDParser**: Extracts pool IDs from JavaScript
- **PoolHTMLParser**: Parses individual pool HTML
- **PoolResultsParser**: Parses pool results JSON
- **TableauParser**: Parses DE bracket HTML

#### 3. Cache Layer
- In-memory cache for development
- Redis for production
- TTL: 3 minutes during active competition, 10 minutes for completed events
- Cache key format: `ftl:{eventId}:{roundId}:{type}`

#### 4. Service Layer
- **PoolService**: Orchestrates pool data fetching
- **DEService**: Orchestrates DE data fetching
- **FencerTrackingService**: Filters for tracked fencers

#### 5. API Layer
- REST endpoints for frontend to consume
- WebSocket for real-time updates (future enhancement)

---

## Parsing Strategies

### Pool ID Extraction

**Input:** HTML string
**Output:** Array of pool ID strings

```python
import re

def extract_pool_ids(html: str) -> list[str]:
    """
    Extract pool IDs from JavaScript variable in HTML.

    Example input:
        var ids = [
            "130C4C6606F342AFBD607A193F05FAB1",
            "BAB54F30F50544188F2EA794B021A72B"
        ];

    Returns: ['130C4C6606F342AFBD607A193F05FAB1', 'BAB54F30F50544188F2EA794B021A72B']
    """
    # Find the var ids = [...]; block
    pattern = r'var ids = \[(.*?)\];'
    match = re.search(pattern, html, re.DOTALL)

    if not match:
        raise ValueError("Could not find pool IDs in HTML")

    ids_string = match.group(1)

    # Extract individual IDs (remove quotes and whitespace)
    ids = re.findall(r'"([A-F0-9]{32})"', ids_string)

    return ids
```

### Pool HTML Parsing

**Input:** HTML fragment
**Output:** PoolAssignment objects

```python
from bs4 import BeautifulSoup
from typing import Optional

def parse_pool_html(html: str) -> dict:
    """
    Parse individual pool HTML to extract strip and fencer data.

    Returns dict with:
    - pool_number: int
    - strip: str | None
    - fencers: list[dict]
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Extract pool number
    pool_num_elem = soup.find('h4', class_='poolNum')
    pool_number = None
    if pool_num_elem:
        # "Pool #1" -> 1
        match = re.search(r'Pool #(\d+)', pool_num_elem.text)
        if match:
            pool_number = int(match.group(1))

    # Extract strip assignment
    strip_elem = soup.find('span', class_='poolStripTime')
    strip = None
    if strip_elem:
        # "On strip H1" -> "H1"
        match = re.search(r'strip\s+([A-Z]\d+)', strip_elem.text)
        if match:
            strip = match.group(1)

    # Extract fencers
    fencers = []
    fencer_rows = soup.find_all('tr', class_='poolRow')

    for row in fencer_rows:
        # Fencer name
        name_elem = row.find('span', class_='poolCompName')
        if not name_elem:
            continue

        name = name_elem.text.strip()

        # Club affiliation
        affil_elem = row.find('span', class_='poolAffil')
        club = affil_elem.text.strip() if affil_elem else None

        # Pool position
        pos_elem = row.find('td', class_='poolPos')
        position = int(pos_elem.text.strip()) if pos_elem else None

        # Results (V, V/M, TS, TR, Ind)
        result_elems = row.find_all('td', class_='poolResult')
        if len(result_elems) >= 5:
            victories = int(result_elems[0].text.strip())
            vm_ratio = float(result_elems[1].text.strip())
            ts = int(result_elems[2].text.strip())
            tr = int(result_elems[3].text.strip())
            indicator_text = result_elems[4].text.strip()
            indicator = int(indicator_text.replace('+', ''))
        else:
            victories = vm_ratio = ts = tr = indicator = None

        fencers.append({
            'name': name,
            'club': club,
            'position': position,
            'victories': victories,
            'vm_ratio': vm_ratio,
            'touches_scored': ts,
            'touches_received': tr,
            'indicator': indicator
        })

    return {
        'pool_number': pool_number,
        'strip': strip,
        'fencers': fencers
    }
```

### Pool Results JSON Parsing

**Input:** JSON string
**Output:** PoolResult objects

```python
import json

def parse_pool_results(json_string: str) -> list[dict]:
    """
    Parse pool results JSON.

    Returns list of fencer results with advancement status.
    """
    data = json.loads(json_string)

    results = []
    for fencer in data:
        results.append({
            'id': fencer['id'],
            'name': fencer['name'],
            'club': fencer.get('club1'),
            'club2': fencer.get('club2'),
            'division': fencer.get('div'),
            'country': fencer['country'],
            'place': fencer['place'],
            'victories': fencer['v'],
            'matches': fencer['m'],
            'vm_ratio': fencer['vm'],
            'touches_scored': fencer['ts'],
            'touches_received': fencer['tr'],
            'indicator': fencer['ind'],
            'advanced': fencer['prediction'] == 'Advanced',
            'tie': fencer['tie']
        })

    return results
```

### Tableau HTML Parsing

**Input:** HTML string
**Output:** DEMatch objects

```python
def parse_tableau_html(html: str, tracked_fencers: list[str]) -> list[dict]:
    """
    Parse DE tableau HTML to find tracked fencers' matches.

    Args:
        html: Tableau HTML
        tracked_fencers: List of fencer names to track (e.g., ["WANG justin"])

    Returns list of matches for tracked fencers.
    """
    soup = BeautifulSoup(html, 'html.parser')

    matches = []

    # Find all score cells
    score_cells = soup.find_all('span', class_='tsco')

    for cell in score_cells:
        parent_row = cell.find_parent('tr')
        if not parent_row:
            continue

        # Find fencer name in this row or nearby rows
        last_name_elem = parent_row.find('span', class_='tcln')
        first_name_elem = parent_row.find('span', class_='tcfn')

        if not (last_name_elem and first_name_elem):
            continue

        fencer_name = f"{last_name_elem.text.strip()} {first_name_elem.text.strip()}"

        # Only process if this is a tracked fencer
        if fencer_name not in tracked_fencers:
            continue

        # Extract score
        score_text = cell.text.strip()

        if score_text == '\xa0' or score_text == '':
            # Future match
            status = 'upcoming'
            score = None
            strip = None
            time = None
        else:
            # Completed match
            status = 'completed'

            # Parse score (e.g., "15 - 9")
            score_match = re.search(r'(\d+)\s*-\s*(\d+)', score_text)
            if score_match:
                score = {
                    'fencer': int(score_match.group(1)),
                    'opponent': int(score_match.group(2))
                }
            else:
                score = None

            # Find referee info (contains strip and time)
            ref_elem = cell.find('span', class_='tref')
            if ref_elem:
                ref_text = ref_elem.text

                # Extract strip (e.g., "Strip L1")
                strip_match = re.search(r'Strip\s+([A-Z]\d+)', ref_text)
                strip = strip_match.group(1) if strip_match else None

                # Extract time (e.g., "11:31 AM")
                time_match = re.search(r'(\d{1,2}:\d{2}\s+[AP]M)', ref_text)
                time = time_match.group(1) if time_match else None
            else:
                strip = None
                time = None

        matches.append({
            'fencer_name': fencer_name,
            'status': status,
            'score': score,
            'strip': strip,
            'time': time
        })

    return matches
```

---

## Caching & Performance

### Caching Strategy

**During Active Pools:**
- Cache TTL: **3 minutes**
- Why: Pools update frequently as bouts complete
- Impact: Max 20 fetches per hour (acceptable load)

**After Pools Complete:**
- Cache TTL: **10 minutes** or until DEs start
- Why: Results are static
- Impact: Minimal server load

**During Active DEs:**
- Cache TTL: **2 minutes**
- Why: DE matches are shorter, need more frequent updates
- Impact: Max 30 fetches per hour

**Cache Keys:**
```
ftl:pool_ids:{eventId}:{roundId}
ftl:pool:{eventId}:{roundId}:{poolId}
ftl:pool_results:{eventId}:{roundId}
ftl:tableau:{eventId}:{roundId}
```

### Performance Optimization

#### Parallel Fetching

Fetch multiple pools simultaneously:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_all_pools(event_id: str, round_id: str, pool_ids: list[str]) -> list[dict]:
    """Fetch all pools in parallel."""
    results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all requests
        future_to_pool = {
            executor.submit(
                fetch_pool_html,
                event_id,
                round_id,
                pool_id
            ): pool_id
            for pool_id in pool_ids
        }

        # Collect results as they complete
        for future in as_completed(future_to_pool):
            pool_id = future_to_pool[future]
            try:
                html = future.result(timeout=10)
                pool_data = parse_pool_html(html)
                pool_data['pool_id'] = pool_id
                results.append(pool_data)
            except Exception as e:
                print(f"Error fetching pool {pool_id}: {e}")

    return results
```

**Performance:**
- Sequential: 45 pools × 500ms = 22.5 seconds ❌
- Parallel (10 workers): 45 pools / 10 × 500ms = 2.3 seconds ✅

#### Selective Fetching

Only fetch pools containing tracked fencers (requires fencer→pool mapping):

```python
def fetch_tracked_pools_only(event_id, round_id, tracked_fencers):
    """
    More efficient: Only fetch pools containing tracked fencers.

    Requires mapping of fencer names to pool IDs.
    This mapping could come from pool results JSON or be cached.
    """
    # First, get pool results to know which pools to fetch
    results_json = fetch_pool_results(event_id, round_id)

    # Map fencers to pool IDs (would need pool number from somewhere)
    # This is a limitation - pool results don't include pool numbers
    # So you may need to fetch all pools at least once to build this map

    # For now, fetch all pools but cache aggressively
    pass
```

**Trade-off:** Pool results JSON doesn't include pool numbers, so you can't easily map fencers to specific pools without fetching them all at least once.

**Recommended Approach:**
1. Fetch all 45 pools once (2-3 seconds)
2. Build fencer→pool mapping
3. Cache mapping for duration of pool rounds
4. On subsequent requests, only re-fetch pools with tracked fencers

---

## Risk Assessment

### Technical Risks

| Risk | Severity | Likelihood | Mitigation | Impact |
|------|----------|------------|------------|---------|
| HTML structure changes | Medium | Medium | Defensive parsing, version detection, unit tests | Scraper breaks until fixed (~1 day) |
| Rate limiting | Low | Low | Respect 3-min cache, max 10 concurrent requests | Temporary inability to fetch data |
| Pool IDs not in JavaScript | Low | Very Low | Already confirmed location; have fallback to scan HTML | Would need alternate discovery method |
| FTL website downtime | Medium | Low | Handle gracefully, show cached data | Users see stale data during outage |
| Missing strip assignments | Low | Low | Some pools may not have strips assigned yet | Show "Strip TBD" to user |

### Legal/Ethical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Terms of Service violation | Low | Review FTL ToS; scraping public data is generally acceptable |
| Excessive load on FTL servers | Very Low | Aggressive caching (3-5 min), reasonable request rate |
| Data accuracy liability | Medium | Add disclaimer: "Data sourced from FTL, accuracy not guaranteed" |

### Operational Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Scraper maintenance burden | Medium | Build robust parsers, add monitoring, create alerts for failures |
| No official API = no support | Low | Expected; have backup plan (manual checking of FTL) |
| Competition from official FTL app | Low | Our app offers different UX (coach-focused, club-specific filtering) |

**Overall Risk Level: LOW-MEDIUM** - Acceptable for MVP/Phase 2

---

## Code Examples

### Complete Pool Fetching Workflow

```python
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import re

class FTLPoolScraper:
    BASE_URL = "https://www.fencingtimelive.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'FencerSchedulesApp/1.0'
        })

    def get_pool_ids(self, event_id: str, round_id: str) -> list[str]:
        """Fetch and extract pool IDs."""
        url = f"{self.BASE_URL}/pools/scores/{event_id}/{round_id}"
        response = self.session.get(url, timeout=10)
        response.raise_for_status()

        # Extract pool IDs from JavaScript
        pattern = r'var ids = \[(.*?)\];'
        match = re.search(pattern, response.text, re.DOTALL)

        if not match:
            raise ValueError("Could not find pool IDs")

        ids_string = match.group(1)
        pool_ids = re.findall(r'"([A-F0-9]{32})"', ids_string)

        return pool_ids

    def fetch_pool(self, event_id: str, round_id: str, pool_id: str) -> str:
        """Fetch single pool HTML."""
        url = f"{self.BASE_URL}/pools/scores/{event_id}/{round_id}/{pool_id}"
        params = {'dbut': 'true'}

        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()

        return response.text

    def parse_pool(self, html: str) -> dict:
        """Parse pool HTML."""
        soup = BeautifulSoup(html, 'html.parser')

        # Pool number
        pool_num_elem = soup.find('h4', class_='poolNum')
        pool_number = None
        if pool_num_elem:
            match = re.search(r'Pool #(\d+)', pool_num_elem.text)
            pool_number = int(match.group(1)) if match else None

        # Strip assignment
        strip_elem = soup.find('span', class_='poolStripTime')
        strip = None
        if strip_elem:
            match = re.search(r'strip\s+([A-Z]\d+)', strip_elem.text)
            strip = match.group(1) if match else None

        # Fencers
        fencers = []
        for row in soup.find_all('tr', class_='poolRow'):
            name_elem = row.find('span', class_='poolCompName')
            if not name_elem:
                continue

            affil_elem = row.find('span', class_='poolAffil')

            fencers.append({
                'name': name_elem.text.strip(),
                'club': affil_elem.text.strip() if affil_elem else None
            })

        return {
            'pool_number': pool_number,
            'strip': strip,
            'fencers': fencers
        }

    def get_all_pools(self, event_id: str, round_id: str) -> list[dict]:
        """Fetch and parse all pools for an event."""
        # Step 1: Get pool IDs
        pool_ids = self.get_pool_ids(event_id, round_id)
        print(f"Found {len(pool_ids)} pools")

        # Step 2: Fetch all pools in parallel
        pools = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_pool = {
                executor.submit(self.fetch_pool, event_id, round_id, pid): pid
                for pid in pool_ids
            }

            for future in future_to_pool:
                pool_id = future_to_pool[future]
                try:
                    html = future.result(timeout=10)
                    pool_data = self.parse_pool(html)
                    pool_data['pool_id'] = pool_id
                    pools.append(pool_data)
                except Exception as e:
                    print(f"Error with pool {pool_id}: {e}")

        return pools

    def find_fencer_strip(self, event_id: str, round_id: str, fencer_name: str) -> dict:
        """Find which strip a specific fencer is on."""
        pools = self.get_all_pools(event_id, round_id)

        for pool in pools:
            for fencer in pool['fencers']:
                if fencer_name.lower() in fencer['name'].lower():
                    return {
                        'fencer': fencer['name'],
                        'pool': pool['pool_number'],
                        'strip': pool['strip'],
                        'club': fencer['club']
                    }

        return None

# Usage
if __name__ == '__main__':
    scraper = FTLPoolScraper()

    event_id = "54B9EF9A9707492E93F1D1F46CF715A2"
    round_id = "D6890CA440324D9E8D594D5682CC33B7"

    # Find where WANG justin is fencing
    result = scraper.find_fencer_strip(event_id, round_id, "WANG justin")

    if result:
        print(f"{result['fencer']} is in Pool #{result['pool']} on {result['strip']}")
    else:
        print("Fencer not found")
```

### Pool Results Fetching

```python
import requests

def get_pool_results(event_id: str, round_id: str) -> list[dict]:
    """Fetch pool results JSON."""
    url = f"https://www.fencingtimelive.com/pools/results/data/{event_id}/{round_id}"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    results = response.json()

    # Process and return
    processed = []
    for fencer in results:
        processed.append({
            'name': fencer['name'],
            'place': fencer['place'],
            'club': fencer.get('club1'),
            'advanced': fencer['prediction'] == 'Advanced',
            'indicator': fencer['ind']
        })

    return processed

def get_club_advancement(event_id: str, round_id: str, club_name: str) -> dict:
    """Get advancement status for all fencers from a club."""
    results = get_pool_results(event_id, round_id)

    club_fencers = [
        f for f in results
        if f['club'] and club_name.lower() in f['club'].lower()
    ]

    advanced = [f for f in club_fencers if f['advanced']]
    eliminated = [f for f in club_fencers if not f['advanced']]

    return {
        'advanced': advanced,
        'eliminated': eliminated,
        'total': len(club_fencers)
    }

# Usage
event_id = "54B9EF9A9707492E93F1D1F46CF715A2"
round_id = "D6890CA440324D9E8D594D5682CC33B7"

cfc_results = get_club_advancement(event_id, round_id, "CFC")
print(f"CFC: {len(cfc_results['advanced'])} advanced, {len(cfc_results['eliminated'])} eliminated")
```

---

## Testing Data

### Reference Event (November NAC 2025 - Div I Men's Épée)

**Event ID:** `54B9EF9A9707492E93F1D1F46CF715A2`
**Pool Round ID:** `D6890CA440324D9E8D594D5682CC33B7`
**DE Round ID:** `08DE5802C0F34ABEBBB468A9681713E7`

**Number of Pools:** 45
**Example Pool ID:** `130C4C6606F342AFBD607A193F05FAB1`

### Test URLs

```
# Pool IDs list
https://www.fencingtimelive.com/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7

# Individual pool (Pool #1)
https://www.fencingtimelive.com/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7/130C4C6606F342AFBD607A193F05FAB1?dbut=true

# Pool results JSON
https://www.fencingtimelive.com/pools/results/data/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7

# DE Tableau
https://www.fencingtimelive.com/tableaus/scores/54B9EF9A9707492E93F1D1F46CF715A2/08DE5802C0F34ABEBBB468A9681713E7
```

### Sample Fencers for Testing

| Name | Club | Pool | Expected Strip | Advanced? |
|------|------|------|----------------|-----------|
| WANG justin | CFC | #7 | TBD | Yes (place 98) |
| IMREK Elijah S. | NOTREDAME / Alliance | #TBD | TBD | Yes (place 1) |
| GAO Daniel | CFC | #TBD | TBD | Yes (place 2) |

### Unit Test Data

Save sample HTML/JSON responses in test fixtures:
```
tests/fixtures/
  pool_ids_response.html
  pool_individual.html
  pool_results.json
  tableau_de.html
```

Use these for offline unit testing of parsers.

---

## Next Steps for Implementation

### Phase 1: Core Scraper (Week 1)

**Day 1-2: Setup**
- [ ] Create Python project structure
- [ ] Install dependencies (requests, beautifulsoup4, pytest)
- [ ] Set up git repository
- [ ] Create test fixtures from saved HTML/JSON

**Day 3-4: Parser Development**
- [ ] Implement pool ID extractor
- [ ] Implement pool HTML parser
- [ ] Implement pool results JSON parser
- [ ] Implement tableau parser
- [ ] Write unit tests for each parser

**Day 5-7: Scraper Service**
- [ ] Build HTTP client with rate limiting
- [ ] Implement parallel fetching
- [ ] Add error handling and retries
- [ ] Integration tests with live data

### Phase 2: Caching & API (Week 2)

**Day 1-2: Cache Layer**
- [ ] Implement in-memory cache
- [ ] Add cache invalidation logic
- [ ] Test cache performance

**Day 3-5: API Endpoints**
- [ ] Build REST API (Flask or FastAPI)
- [ ] Endpoints: `/api/pools/{eventId}`, `/api/de/{eventId}`, `/api/fencer/{name}`
- [ ] Add request validation
- [ ] API documentation (OpenAPI/Swagger)

**Day 6-7: Deployment**
- [ ] Containerize with Docker
- [ ] Deploy to cloud (Heroku, Railway, or DigitalOcean)
- [ ] Set up monitoring

### Phase 3: Frontend (Week 3)

**Day 1-3: Basic UI**
- [ ] Mobile-first responsive layout
- [ ] Fencer search page
- [ ] Pool strip display page
- [ ] Advancement status page

**Day 4-5: Polish**
- [ ] Add loading states
- [ ] Error handling UI
- [ ] Auto-refresh during active competition

**Day 6-7: Testing**
- [ ] User acceptance testing
- [ ] Performance optimization
- [ ] Bug fixes

### Phase 4: Live Tournament Testing (Week 4)

- [ ] Test at actual tournament
- [ ] Gather coach feedback
- [ ] Fix issues discovered in production
- [ ] Iterate on UX

---

## Appendix A: HTML Structure Reference

### Pool HTML - Complete Structure

```html
<table>
    <tr>
        <td><h4 class="poolNum">Pool #1</h4></td>
        <td><a href="/pools/details/..." class="btn btn-primary btn-sm">Details</a></td>
    </tr>
</table>

<span class="poolStripTime">
    On strip H1
</span>

<table class="table table-condensed table-sm table-bordered poolTable">
    <thead>
        <tr class="poolHeader">
            <th class="poolNameCol"></th>
            <th class="poolPosCol"></th>
            <th>1</th><th>2</th><th>3</th>...
            <th class="poolSepCol"></th>
            <th class="poolResCol">V</th>
            <th class="poolResCol">V / M</th>
            <th class="poolResCol">TS</th>
            <th class="poolResCol">TR</th>
            <th class="poolResCol">Ind</th>
        </tr>
    </thead>
    <tbody>
        <tr class="poolRow">
            <td>
                <span class="poolCompName">IMREK Samuel A.</span>
                <br /><span class="poolAffil">ALLIANCEFA / Gulf Coast / USA</span>
            </td>
            <td class="poolPos">1</td>

            <!-- Bout results -->
            <td class="poolScoreFill"></td>  <!-- Own position -->
            <td class="poolScore poolScoreV">
                <span>V5</span>  <!-- Victory, 5 touches -->
            </td>
            <td class="poolScore poolScoreV">
                <span>V5</span>
            </td>
            <!-- ... more bouts ... -->

            <td class="poolSep"></td>

            <!-- Summary stats -->
            <td class="poolResult">6</td>      <!-- Victories -->
            <td class="poolResult">1.00</td>   <!-- V/M -->
            <td class="poolResult">27</td>     <!-- TS -->
            <td class="poolResult">13</td>     <!-- TR -->
            <td class="poolResult">+14</td>    <!-- Indicator -->
        </tr>
        <!-- More fencers... -->
    </tbody>
</table>

<div class="poolRefsDiv">
    <span class="poolRefsHeader">Referee(s)</span>
    <br/>
    <span class="poolRefName">HASHIM Aya</span>
    <br />
    <span class="poolAffil">Metropolitan NYC / EGY</span>
    <br />
</div>
```

### Tableau HTML - Complete Structure

```html
<table class='elimTableau w-100'>
    <tr>
        <th>Table of 256</th>
        <th>Table of 128</th>
        <th>Table of 64</th>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <!-- Match pair starts -->
    <tr>
        <!-- First fencer -->
        <td class='tbb'>  <!-- tbb = top bracket bout -->
            <span class='tseed'>(1)&nbsp;</span>
            <span class='tcln'>IMREK</span>
            <span class='tcfn'>Elijah</span>
            <span class='tcaff'>
                <br/>
                NOTREDAME / Gulf Coast / USA
            </span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <!-- Match result -->
        <td class='tbr tscoref'>&nbsp;</td>  <!-- tbr = top bracket result -->
        <td class='tbb'>
            <!-- Winner advances here -->
            <span class='tseed'>(1)&nbsp;</span>
            <span class='tcln'>IMREK</span>
            <span class='tcfn'>Elijah</span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <!-- Second fencer -->
        <td class='tbbr'>  <!-- tbbr = top/bottom bracket result -->
            <span class='tseed'>(256)&nbsp;</span>
            <span class='tcln'>- BYE -</span>
            &nbsp;
        </td>
        <td class='tbr tscoref'>
            <span class='tsco'>&nbsp;</span>  <!-- Empty = match not yet played -->
        </td>
        <td>&nbsp;</td>
    </tr>

    <!-- Completed match with score -->
    <tr>
        <td class='tbr tscoref'>&nbsp;</td>
        <td class='tbr'>&nbsp;</td>
        <td class='tbb'>
            <span class='tseed'>(1)&nbsp;</span>
            <span class='tcln'>IMREK</span>
            <span class='tcfn'>Elijah</span>
            &nbsp;
        </td>
    </tr>

    <tr>
        <td class='tbb'>
            <span class='tseed'>(129)&nbsp;</span>
            <span class='tcln'>WU</span>
            <span class='tcfn'>Alistair</span>
            &nbsp;
        </td>
        <td class='tbr'>&nbsp;</td>
        <td class='tbr tscoref'>
            <span class='tsco'>
                15 - 8<br/>  <!-- Score -->
                <span class='tref'>
                    Ref ALFORD April C. FIT / North Texas / USA
                </span>
                <br/>
                <span class='tref'>11:31 AM &#160;Strip L1</span>  <!-- Time and strip -->
                &nbsp;
            </span>
        </td>
    </tr>

    <!-- Loser does NOT appear in next column -->
    <tr>
        <td class='tbr tscoref'>&nbsp;</td>
        <td class='tbbr'>
            <span class='tseed'>(129)&nbsp;</span>
            <span class='tcln'>WU</span>
            <span class='tcfn'>Alistair</span>
            &nbsp;
        </td>
        <td class='tbr'>&nbsp;</td>
    </tr>

    <!-- Pattern repeats... -->
</table>
```

---

## Appendix B: Error Handling

### Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| Pool IDs not found | JavaScript format changed | Update regex pattern; add fallback to scan HTML for pool div IDs |
| Strip assignment missing | Pool not yet assigned to strip | Display "Strip TBD" to user |
| Timeout fetching pools | Slow FTL response or network issue | Implement retries (3x with exponential backoff) |
| HTML parsing fails | FTL changed structure | Log error, alert developer, return cached data if available |
| Pool results 404 | Pools not complete yet | Handle gracefully, show message "Pool results not available yet" |

### Defensive Parsing Example

```python
def safe_parse_pool(html: str) -> dict:
    """Parse pool with defensive error handling."""
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Try to get pool number
        try:
            pool_num_elem = soup.find('h4', class_='poolNum')
            pool_number = int(re.search(r'Pool #(\d+)', pool_num_elem.text).group(1))
        except (AttributeError, ValueError):
            pool_number = None
            logger.warning("Could not extract pool number")

        # Try to get strip
        try:
            strip_elem = soup.find('span', class_='poolStripTime')
            strip = re.search(r'strip\s+([A-Z]\d+)', strip_elem.text).group(1)
        except (AttributeError, ValueError):
            strip = None
            logger.info("Strip not assigned yet")

        # Always return something, even if partial
        return {
            'pool_number': pool_number,
            'strip': strip,
            'fencers': [],  # Would parse fencers similarly
            'parse_success': True,
            'parse_warnings': []
        }

    except Exception as e:
        logger.error(f"Critical parsing error: {e}")
        return {
            'pool_number': None,
            'strip': None,
            'fencers': [],
            'parse_success': False,
            'parse_error': str(e)
        }
```

---

## Document Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-20 | Initial release - complete API specification |

---

## Credits

**Research conducted by:** AI Technical Advisor + Frank (Human Developer)
**Research dates:** November 20, 2025
**Test event:** November NAC 2025 - Division I Men's Épée
**FencingTimeLive version observed:** 2.0.20251030.042115

---

**END OF SPECIFICATION**
