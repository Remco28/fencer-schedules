# FTL Research: Event Page Structure (Round Discovery)

**Date:** 2026-01-15
**Source:** https://www.fencingtimelive.com/events/view/{event_id}

## URL Pattern

```
https://www.fencingtimelive.com/events/view/{event_id}
```

Note: This URL redirects to `/events/results/{event_id}` for completed events.

## Key Finding: Navigation Links Contain Round IDs

The event page navigation contains direct links to pool and DE rounds:

```html
<li class="nav-item">
    <a class="nav-link waves-light"
       href="/pools/scores/7A76D82961504CC7A885D0E0E60D60C3/5610A0F90E36406CA634B86053BCD6D8">
        <img class="ftmenuicon" src="/img/poolInverse.png"><br>Pools
    </a>
</li>

<li class="nav-item">
    <a class="nav-link waves-light"
       href="/tableaus/scores/7A76D82961504CC7A885D0E0E60D60C3/BC0A8665F5CD45DE9DA9024724076EAC">
        <img class="ftmenuicon" src="/img/tableauInverse.png"><br>Tableau
    </a>
</li>
```

## URL Patterns for Rounds

| Round Type | URL Pattern |
|------------|-------------|
| Pool Round | `/pools/scores/{event_id}/{pool_round_id}` |
| DE Tableau | `/tableaus/scores/{event_id}/{de_round_id}` |
| Pool Results | `/pools/results/{event_id}/{pool_round_id}` |
| Seeding | `/rounds/seeding/{event_id}/{round_id}` |
| Strips | `/rounds/strips/{event_id}/{round_id}` |

## Parsing Strategy

```python
import re
from bs4 import BeautifulSoup

def extract_round_ids(html: str, event_id: str) -> dict:
    """Extract pool and DE round IDs from event page."""
    soup = BeautifulSoup(html, 'html.parser')

    result = {
        'event_id': event_id,
        'pool_round_id': None,
        'de_round_id': None,
    }

    # Find pool round link
    pool_link = soup.find('a', href=re.compile(r'/pools/scores/'))
    if pool_link:
        match = re.search(r'/pools/scores/[^/]+/([A-Fa-f0-9]{32})', pool_link['href'])
        if match:
            result['pool_round_id'] = match.group(1)

    # Find DE tableau link
    tableau_link = soup.find('a', href=re.compile(r'/tableaus/scores/'))
    if tableau_link:
        match = re.search(r'/tableaus/scores/[^/]+/([A-Fa-f0-9]{32})', tableau_link['href'])
        if match:
            result['de_round_id'] = match.group(1)

    return result
```

## Sample Data

**Event:** Junior Women's Saber (Junior Olympics)

| Field | Value |
|-------|-------|
| Event ID | `7A76D82961504CC7A885D0E0E60D60C3` |
| Pool Round ID | `5610A0F90E36406CA634B86053BCD6D8` |
| DE Round ID | `BC0A8665F5CD45DE9DA9024724076EAC` |

## Navigation Tab Classes

| Tab | Icon/Class | Link Pattern |
|-----|------------|--------------|
| Schedule | `fa-calendar-alt` | `/tournaments/eventSchedule/{tournament_id}` |
| My Fencers | `fa-heart` | `/tournaments/myFencers/{tournament_id}` |
| Fencers | `fa-user` | `/events/competitors/{event_id}` |
| Format | `fa-info-circle` | `/events/format/{event_id}` |
| Pools | `poolInverse.png` | `/pools/scores/{event_id}/{pool_round_id}` |
| Seeding | `fa-list-ol` | `/rounds/seeding/{event_id}/{round_id}` |
| Strips | `fa-hand-point-right` | `/rounds/strips/{event_id}/{round_id}` |
| Pool Results | `fa-arrows-alt-v` | `/pools/results/{event_id}/{pool_round_id}` |
| Tableau | `tableauInverse.png` | `/tableaus/scores/{event_id}/{de_round_id}` |
| Results | `fa-trophy` | `/events/results/{event_id}` |
| Scores | `machineInverse.png` | `/tournaments/liveScores/{tournament_id}` |

## Edge Cases

1. **Events without pools:** Some team events may skip directly to DE
2. **Events not started:** Pool/Tableau links may not appear yet
3. **Multiple rounds:** Large events may have preliminary + final pools (needs verification)

## Pool Page: Pool IDs in JavaScript

The pool scores page embeds pool IDs in JavaScript:

```html
<script>
    var eid = "7A76D82961504CC7A885D0E0E60D60C3";
    var rid = "5610A0F90E36406CA634B86053BCD6D8";
    var ids = [
        "A61721D8265448DDB330A838BBC1B0F8",
        "AF420152ECF94E73B968BEF4F315C9B0",
        // ... 37 pool IDs total
    ];
</script>
```

This matches our existing `pool_ids.py` parser.
