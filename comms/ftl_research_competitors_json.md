# FTL Research: Competitors JSON Endpoint

**Date:** 2026-01-15
**Source:** https://www.fencingtimelive.com/events/competitors/data/{event_id}

## URL Pattern

```
https://www.fencingtimelive.com/events/competitors/data/{event_id}
```

Returns JSON array of all competitors in an event.

## Response Structure

```json
[
  {
    "id": "3AA8FC63D88940F19D50E766AA06FE51",
    "status": "CheckedIn",
    "name": "ANDRES Charmaine G.",
    "club1": "Cali Fencing",
    "club2": null,
    "clubNames": "Cali Fencing",
    "div": "Southern California",
    "country": "USA",
    "weaponRating": "A25",
    "weaponRatingSort": 5259995,
    "rank": 5,
    "rankSort": 5,
    "search": "andres charmaine g.|cali fencing|southern california|usa|a25"
  },
  {
    "id": "AAD8E36E204D4BCA85AFA0B192EDCACC",
    "status": "CheckedIn",
    "name": "ANTHONY Alexia B.",
    "club1": "Peter Westbrook Foundation",
    "club2": "Tim Morehouse Fencing Club",
    "clubNames": "Peter Westbrook Foundation / Tim Morehouse Fencing Club",
    "div": "New Jersey",
    "country": "USA",
    "weaponRating": "A24",
    "weaponRatingSort": 5249977,
    "rank": 23,
    "rankSort": 23,
    "search": "anthony alexia b.|peter westbrook foundation|tim morehouse fencing club|new jersey|usa|a24"
  }
]
```

## Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Fencer UUID (32-char hex) |
| `status` | string | Check-in status ("CheckedIn", etc.) |
| `name` | string | Full name (LASTNAME Firstname M.) |
| `club1` | string | Primary club name |
| `club2` | string\|null | Secondary club name (if any) |
| `clubNames` | string | Combined club names (for display) |
| `div` | string | USFA Division |
| `country` | string | Country code |
| `weaponRating` | string | Rating (e.g., "A25", "B24", "U") |
| `weaponRatingSort` | int | Numeric rating for sorting |
| `rank` | int\|null | National ranking |
| `rankSort` | int | Rank for sorting (9999 if unranked) |
| `search` | string | Lowercase search string |

## Club Matching Strategy

For filtering fencers by club:

```python
def match_club(fencer: dict, club_filter: str) -> bool:
    """Check if fencer matches club filter."""
    filter_lower = club_filter.lower().strip()

    # Check primary club
    club1 = (fencer.get('club1') or '').lower()
    if filter_lower in club1 or club1 in filter_lower:
        return True

    # Check secondary club
    club2 = (fencer.get('club2') or '').lower()
    if club2 and (filter_lower in club2 or club2 in filter_lower):
        return True

    # Check combined names
    club_names = (fencer.get('clubNames') or '').lower()
    if filter_lower in club_names:
        return True

    return False
```

## Sample Club Values

| Club Name | Frequency |
|-----------|-----------|
| Cali Fencing | Common in SoCal |
| Peter Westbrook Foundation | NYC area |
| Durkan Fencing Academy | NJ area |
| Lilov Fencing Academy | NJ area |
| Sol Fencing Academy | San Diego |

## Usage for Club-Based Tracking

1. Fetch competitors JSON for each event
2. Filter by club name (substring match)
3. Build list of fencer names to track
4. Match against pool/results data

## Integration with Existing Parsers

The competitors JSON provides authoritative club data. Our existing parsers:

- `pool_results.py`: Has `club_primary` field but may be less complete
- `pools.py`: Has `club` field from pool roster

For best results, use competitors JSON as primary source for club filtering, then correlate with pool/results data by fencer name.
