# FTL Research: Tournament Schedule Page Structure

**Date:** 2026-01-15
**Source:** https://www.fencingtimelive.com/tournaments/eventSchedule/{tournament_id}

## URL Pattern

```
https://www.fencingtimelive.com/tournaments/eventSchedule/{tournament_id}
```

Example: `BBA4B7FACC464C93BA534ACE381A6C46` (Junior Olympics)

## HTML Structure

### Date Headers

Days are separated by `<h5>` tags:

```html
<h5>Friday January 9, 2026</h5>
<h5>Saturday January 10, 2026</h5>
```

### Event Table

Each day has a table with class `scheduleTable`:

```html
<table class="scheduleTable table table-sm table-hover hoverHand w-100">
    <thead class="ftblue yellow-text">
        <tr>
            <th style="width: 10%;">Start</th>
            <th style="width: 30%;">Event</th>
            <th style="width: auto;">Status</th>
        </tr>
    </thead>
    <tbody>
        <!-- Event rows -->
    </tbody>
</table>
```

### Event Row Structure

```html
<tr id="ev_7A76D82961504CC7A885D0E0E60D60C3"
    class="clickable-row"
    data-href="/events/view/7A76D82961504CC7A885D0E0E60D60C3">
    <td>8:00 AM</td>
    <td>
        <a href="/events/view/7A76D82961504CC7A885D0E0E60D60C3">
            <strong>Junior   Women&#x27;s Saber</strong>
        </a>
    </td>
    <td>
        <i class="fas fa-check green-text mr-1"></i>Finished at 2:06 PM
        <span class="ml-3">(255 competitors)</span>
    </td>
</tr>
```

### Key Attributes

| Attribute | Location | Example |
|-----------|----------|---------|
| Event ID | `<tr id="ev_{ID}">` | `ev_7A76D82961504CC7A885D0E0E60D60C3` |
| Event ID | `data-href` | `/events/view/7A76D82961504CC7A885D0E0E60D60C3` |
| Start Time | First `<td>` | `8:00 AM` |
| Event Name | `<strong>` in second `<td>` | `Junior Women's Saber` |
| Status | Third `<td>` | `Finished at 2:06 PM` |
| Competitor Count | `<span>` in status | `(255 competitors)` |

### Status Indicators

- **Finished:** `<i class="fas fa-check green-text">` + "Finished at {time}"
- **In Progress:** (needs live event to verify)
- **Not Started:** (needs live event to verify)

## Parsing Strategy

```python
from bs4 import BeautifulSoup
import re

def parse_tournament_schedule(html: str) -> list[dict]:
    """Parse tournament schedule page to extract events."""
    soup = BeautifulSoup(html, 'html.parser')
    events = []
    current_date = None

    for element in soup.find_all(['h5', 'tr']):
        # Date header
        if element.name == 'h5':
            current_date = element.get_text(strip=True)
            continue

        # Event row
        if element.name == 'tr' and element.get('id', '').startswith('ev_'):
            event_id = element['id'].replace('ev_', '')
            cells = element.find_all('td')

            if len(cells) >= 3:
                start_time = cells[0].get_text(strip=True)
                name_elem = cells[1].find('strong')
                event_name = name_elem.get_text(strip=True) if name_elem else ''
                status_text = cells[2].get_text(strip=True)

                # Extract weapon from name
                weapon = None
                for w in ['Épée', 'Epee', 'Foil', 'Saber', 'Sabre']:
                    if w.lower() in event_name.lower():
                        weapon = w.replace('Épée', 'Epee').replace('Sabre', 'Saber')
                        break

                events.append({
                    'event_id': event_id,
                    'name': event_name,
                    'date': current_date,
                    'start_time': start_time,
                    'weapon': weapon,
                    'status': status_text,
                })

    return events
```

## Sample Data (Junior Olympics)

```json
[
  {
    "event_id": "7A76D82961504CC7A885D0E0E60D60C3",
    "name": "Junior Women's Saber",
    "date": "Friday January 9, 2026",
    "start_time": "8:00 AM",
    "weapon": "Saber",
    "status": "Finished at 2:06 PM (255 competitors)"
  },
  {
    "event_id": "3DC2567322AC4633AAE116463253DCA5",
    "name": "Cadet Women's Épée",
    "date": "Friday January 9, 2026",
    "start_time": "8:00 AM",
    "weapon": "Epee",
    "status": "Finished at 3:08 PM (224 competitors)"
  },
  {
    "event_id": "F5EA6F895F7F46379CBFD96E44307A03",
    "name": "Junior Men's Foil",
    "date": "Friday January 9, 2026",
    "start_time": "1:00 PM",
    "weapon": "Foil",
    "status": "Finished at 8:15 PM (312 competitors)"
  }
]
```

## Related Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/events/view/{event_id}` | Event page (redirects to results) |
| `/events/competitors/{event_id}` | Fencer list page |
| `/events/competitors/data/{event_id}` | **JSON** - Fencer list with clubs |
| `/pools/scores/{event_id}/{pool_round_id}` | Pool scores page |
| `/tableaus/scores/{event_id}/{de_round_id}` | DE tableau page |
