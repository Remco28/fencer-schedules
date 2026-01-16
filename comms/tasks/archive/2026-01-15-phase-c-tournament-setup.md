# Task: Phase C — Tournament Setup & Event Discovery

**Date:** 2026-01-15
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Enable users to set up tournament tracking by entering a FencingTimeLive tournament URL. The app will discover all events, find pool/DE round IDs, fetch competitor lists, and identify fencers matching the user's club.

This is the core "front door" for the new tournament-centric flow.

## User Stories

- As a user, I can paste a FencingTimeLive tournament URL to start tracking.
- As a user, I can filter events by weapon (Epee, Foil, Saber, or all).
- As a user, I can see all events discovered from the tournament.
- As a user, I can see which club fencers were found in each event.
- As a user, I can save the tournament to my tracked list.

## Scope (In)

- Tournament schedule parser (new)
- Event round discovery (new)
- TrackedTournament model (new)
- CachedEvent model (new)
- Tournament setup page with URL input and filters
- Club fencer discovery using competitors JSON endpoint
- List of user's tracked tournaments on dashboard

## Scope (Out)

- Manual fencer add (Phase E)
- Consolidated fencer status dashboard (Phase D)
- Auto-refresh / live updates
- Tournament data cleanup job (Phase F)

## Research Reference

See Phase A research artifacts:
- `comms/ftl_research_tournament_schedule.md` - Schedule page HTML structure
- `comms/ftl_research_event_page.md` - Round ID discovery
- `comms/ftl_research_competitors_json.md` - Club data format

## Deliverables

### 1. New Parsers

#### `app/ftl/parsers/tournament_schedule.py`

```python
"""Parse FencingTimeLive tournament schedule page."""
from bs4 import BeautifulSoup
import re
from typing import Optional

def parse_tournament_schedule(html: str) -> dict:
    """
    Parse tournament schedule page HTML.

    Returns:
        {
            "tournament_name": str,
            "events": [
                {
                    "event_id": str (32-char hex),
                    "name": str,
                    "date": str,
                    "start_time": str,
                    "weapon": str | None (Epee, Foil, Saber),
                    "status": str,
                }
            ]
        }
    """
```

Parsing strategy:
- Tournament name: `<title>` tag or `.tournName` div
- Date headers: `<h5>` tags containing dates
- Event rows: `<tr id="ev_{event_id}">` with `data-href`
- Event name: `<strong>` inside second `<td>`
- Weapon: Extract from name (contains "Épée/Epee", "Foil", "Saber/Sabre")
- Start time: First `<td>` text
- Status: Third `<td>` text

#### `app/ftl/parsers/event_rounds.py`

```python
"""Discover pool and DE round IDs from event page."""
import re
from bs4 import BeautifulSoup
from typing import Optional

def parse_event_rounds(html: str) -> dict:
    """
    Extract pool and DE round IDs from event page navigation.

    Returns:
        {
            "pool_round_id": str | None,
            "de_round_id": str | None,
        }
    """
```

Parsing strategy:
- Find `<a href="/pools/scores/{event_id}/{pool_round_id}">` → extract pool_round_id
- Find `<a href="/tableaus/scores/{event_id}/{de_round_id}">` → extract de_round_id
- Use regex: `r'/pools/scores/[^/]+/([A-Fa-f0-9]{32})'`

### 2. Database Models

Add to `app/models.py`:

```python
class TrackedTournament(Base):
    __tablename__ = "tracked_tournaments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tournament_id = Column(String(32), nullable=False)  # FTL hex ID
    tournament_name = Column(String(300), nullable=False)
    tournament_url = Column(String(500), nullable=False)
    club_filter = Column(String(200), nullable=True)  # defaults to user.club
    weapon_filter = Column(String(20), nullable=True)  # Epee, Foil, Saber, or null
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    user = relationship("User", back_populates="tracked_tournaments")
    events = relationship("CachedEvent", back_populates="tournament", cascade="all, delete-orphan")


class CachedEvent(Base):
    __tablename__ = "cached_events"

    id = Column(Integer, primary_key=True, index=True)
    tracked_tournament_id = Column(Integer, ForeignKey("tracked_tournaments.id"), nullable=False, index=True)
    event_id = Column(String(32), nullable=False)  # FTL hex ID
    event_name = Column(String(300), nullable=False)
    weapon = Column(String(20), nullable=True)
    start_date = Column(String(50), nullable=True)
    start_time = Column(String(20), nullable=True)
    pool_round_id = Column(String(32), nullable=True)
    de_round_id = Column(String(32), nullable=True)
    fencer_count = Column(Integer, default=0)  # club fencers found

    tournament = relationship("TrackedTournament", back_populates="events")
```

Add to User model:
```python
tracked_tournaments = relationship("TrackedTournament", back_populates="user", cascade="all, delete-orphan")
```

### 3. FTL Client Extensions

Add to `app/ftl/client.py`:

```python
def fetch_tournament_schedule(tournament_id: str) -> str:
    """Fetch tournament schedule page HTML."""
    url = f"https://www.fencingtimelive.com/tournaments/eventSchedule/{tournament_id}"
    # Use existing _get with retry/timeout
    return _get(url)

def fetch_event_page(event_id: str) -> str:
    """Fetch event page HTML (follows redirects)."""
    url = f"https://www.fencingtimelive.com/events/view/{event_id}"
    # Use existing _get with retry/timeout, follow redirects
    return _get(url, allow_redirects=True)

def fetch_competitors_json(event_id: str) -> list[dict]:
    """Fetch competitors JSON for an event."""
    url = f"https://www.fencingtimelive.com/events/competitors/data/{event_id}"
    response = _get(url)
    return json.loads(response)
```

### 4. Tournament Setup Routes

**GET /tournament/new** - Render setup form
- Requires authentication
- Pre-fill club filter from user.club
- Weapon filter dropdown (All, Epee, Foil, Saber)

**POST /tournament/new** - Process tournament URL
1. Extract tournament_id from URL (validate format)
2. Fetch tournament schedule page
3. Parse events list
4. Filter by weapon if specified
5. For each matching event:
   - Fetch event page → extract pool/DE round IDs
   - Fetch competitors JSON → filter by club → count matches
6. Create TrackedTournament + CachedEvent records
7. Redirect to tournament detail page

**GET /tournament/{id}** - Show tracked tournament
- List all events with fencer counts
- Links to view pools/DE for each event
- Delete button

**POST /tournament/{id}/delete** - Delete tracked tournament
- Requires CSRF
- Cascade deletes events
- Redirect to dashboard

### 5. Templates

#### `app/templates/tournament_new.html`

```html
{% extends "base.html" %}
{% block title %}Track Tournament{% endblock %}
{% block content %}
<section>
    <h1>Track a Tournament</h1>

    {% if error %}
    <article class="error-message"><p>{{ error }}</p></article>
    {% endif %}

    <form method="post" action="/tournament/new">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

        <label>
            FencingTimeLive Tournament URL
            <input type="url" name="url" value="{{ values.url or '' }}"
                   placeholder="https://www.fencingtimelive.com/tournaments/eventSchedule/..." required>
            <small>Paste the tournament schedule page URL</small>
        </label>

        <label>
            Club Filter
            <input type="text" name="club" value="{{ values.club or user.club or '' }}"
                   placeholder="e.g., Elite Fencers Club">
            <small>Only track fencers from this club (leave empty to skip auto-discovery)</small>
        </label>

        <label>
            Weapon Filter
            <select name="weapon">
                <option value="">All Weapons</option>
                <option value="Epee" {{ 'selected' if values.weapon == 'Epee' }}>Epee</option>
                <option value="Foil" {{ 'selected' if values.weapon == 'Foil' }}>Foil</option>
                <option value="Saber" {{ 'selected' if values.weapon == 'Saber' }}>Saber</option>
            </select>
        </label>

        <button type="submit">Find Events</button>
    </form>
</section>
{% endblock %}
```

#### `app/templates/tournament_detail.html`

```html
{% extends "base.html" %}
{% block title %}{{ tournament.tournament_name }}{% endblock %}
{% block content %}
<section>
    <h1>{{ tournament.tournament_name }}</h1>
    <p>
        {% if tournament.club_filter %}Club: {{ tournament.club_filter }}{% endif %}
        {% if tournament.weapon_filter %} · {{ tournament.weapon_filter }} only{% endif %}
    </p>

    <h2>Events ({{ tournament.events|length }})</h2>

    {% if tournament.events %}
    <table>
        <thead>
            <tr>
                <th>Event</th>
                <th>Date/Time</th>
                <th>Club Fencers</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for event in tournament.events %}
            <tr>
                <td>{{ event.event_name }}</td>
                <td>{{ event.start_date }} {{ event.start_time }}</td>
                <td>{{ event.fencer_count }}</td>
                <td>
                    {% if event.pool_round_id %}
                    <a href="/pools?event_id={{ event.event_id }}&pool_round_id={{ event.pool_round_id }}">Pools</a>
                    {% endif %}
                    {% if event.de_round_id %}
                    <a href="/de?event_id={{ event.event_id }}&de_round_id={{ event.de_round_id }}">DE</a>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p>No events found matching your filters.</p>
    {% endif %}

    <form method="post" action="/tournament/{{ tournament.id }}/delete" style="margin-top: 2rem;">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit" class="outline" onclick="return confirm('Delete this tournament?')">
            Delete Tournament
        </button>
    </form>
</section>
{% endblock %}
```

### 6. Dashboard Update

Update `/dashboard` to show tracked tournaments:

```html
<section>
    <h2>Your Tournaments</h2>
    {% if tournaments %}
    <ul>
        {% for t in tournaments %}
        <li>
            <a href="/tournament/{{ t.id }}">{{ t.tournament_name }}</a>
            <small>{{ t.events|length }} events · {{ t.club_filter or 'No club filter' }}</small>
        </li>
        {% endfor %}
    </ul>
    {% else %}
    <p>No tournaments tracked yet.</p>
    {% endif %}
    <a href="/tournament/new" class="btn">Track a Tournament</a>
</section>
```

### 7. Navigation Update

Add to base.html nav (authenticated section):
```html
<li><a href="/tournament/new">Track Tournament</a></li>
```

### 8. URL Parsing Helper

```python
import re

TOURNAMENT_URL_PATTERN = re.compile(
    r'fencingtimelive\.com/tournaments/(?:eventSchedule|scores)/([A-Fa-f0-9]{32})'
)

def extract_tournament_id(url: str) -> str | None:
    """Extract tournament ID from FTL URL."""
    match = TOURNAMENT_URL_PATTERN.search(url)
    return match.group(1) if match else None
```

### 9. Club Matching Helper

```python
def match_club(fencer: dict, club_filter: str) -> bool:
    """Check if fencer matches club filter (case-insensitive substring)."""
    if not club_filter:
        return False
    filter_lower = club_filter.lower().strip()

    club1 = (fencer.get('club1') or '').lower()
    club2 = (fencer.get('club2') or '').lower()
    club_names = (fencer.get('clubNames') or '').lower()

    return (
        filter_lower in club1 or
        filter_lower in club2 or
        filter_lower in club_names
    )
```

### 10. Tests

Add `tests/ftl/test_tournament_schedule_parser.py`:
- Test parse_tournament_schedule with sample HTML
- Test weapon extraction from event names
- Test date/time parsing
- Test empty events list handling

Add `tests/ftl/test_event_rounds_parser.py`:
- Test parse_event_rounds with sample HTML
- Test missing pool link
- Test missing DE link
- Test both links present

Add `tests/web/test_tournament.py`:
- test_tournament_new_requires_auth
- test_tournament_new_renders
- test_tournament_new_invalid_url
- test_tournament_new_creates_records (mock FTL)
- test_tournament_detail_requires_auth
- test_tournament_detail_renders
- test_tournament_delete_requires_csrf
- test_tournament_delete_removes_records
- test_dashboard_shows_tournaments

## Implementation Notes

- **URL validation:** Accept various FTL URL formats, extract 32-char hex ID
- **Weapon normalization:** "Épée" → "Epee", "Sabre" → "Saber"
- **Rate limiting:** Fetch events sequentially to avoid hammering FTL
- **Error handling:** If one event fails, continue with others, log error
- **Club matching:** Case-insensitive substring match on club1, club2, clubNames
- **Empty club filter:** Skip club fencer discovery if no club specified

## Acceptance Criteria

- [ ] `/tournament/new` renders for authenticated users
- [ ] Valid tournament URL creates TrackedTournament + CachedEvent records
- [ ] Events are filtered by weapon when specified
- [ ] Club fencers are counted for each event
- [ ] `/tournament/{id}` shows event list with fencer counts
- [ ] Delete tournament removes all associated data
- [ ] Dashboard shows list of tracked tournaments
- [ ] All new parser tests pass
- [ ] All web tests pass
- [ ] No regressions to existing functionality
