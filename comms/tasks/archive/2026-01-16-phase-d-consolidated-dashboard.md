# Task: Phase D — Consolidated Dashboard

**Date:** 2026-01-16
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Create a unified dashboard view that aggregates all club fencers across all events in a tracked tournament. The dashboard shows real-time status, location, and activity grouped into "Active Now", "Waiting", and "Finished" sections.

This is the primary user-facing feature that brings together all the tournament tracking components.

## User Stories

- As a user, I can see all my club's fencers across all events in one view.
- As a user, I can see which fencers are currently active (on strip).
- As a user, I can see which fencers are waiting for their next bout.
- As a user, I can see which fencers have finished (eliminated or completed).
- As a user, I can refresh the dashboard to get the latest status.
- As a user, I can click on a fencer to see detailed pool/DE information.

## Scope (In)

- Consolidated dashboard page (`/tournament/{id}/dashboard`)
- Fencer status aggregation logic (orchestration layer)
- Activity grouping (active, waiting, finished)
- Location display (strip, pool number, DE round)
- Manual refresh functionality
- Direct links to pool/DE detail pages

## Scope (Out)

- Auto-refresh (Phase F)
- Manual fencer tracking (Phase E)
- Historical data / past tournaments
- Real-time WebSocket updates

## Dependencies

All these are already implemented:
- `fetch_pools_bundle()` from `app/ftl/client.py`
- `fetch_tableau_raw()` from `app/ftl/client.py`
- `parse_de_tableau()` from `app/ftl/parsers/de_tableau.py`
- TrackedTournament and CachedEvent models
- Club matching logic

## Deliverables

### 1. Orchestration Service

Create `app/services/tournament_service.py`:

```python
"""Tournament fencer status orchestration."""
from typing import Optional
from dataclasses import dataclass
from app.ftl.client import fetch_pools_bundle, fetch_tableau_raw, FTLHTTPError
from app.ftl.parsers.de_tableau import parse_de_tableau


@dataclass
class FencerStatus:
    """Status of a single fencer in a tournament."""
    name: str
    event_id: str
    event_name: str
    weapon: Optional[str]

    # Location
    pool_number: Optional[int] = None
    strip: Optional[str] = None
    de_round: Optional[str] = None  # "64", "32", "16", "QF", "SF", "F"

    # Status
    activity: str = "unknown"  # "active", "waiting", "finished"
    phase: str = "unknown"  # "pools", "de", "complete"
    result: Optional[str] = None  # "Advanced", "Eliminated", "3rd Place", etc.

    # Metadata
    last_updated: str = ""  # ISO timestamp
    error: Optional[str] = None


def get_tournament_fencer_status(
    tournament_id: int,
    club_filter: str,
    cached_events: list,
) -> dict[str, list[FencerStatus]]:
    """
    Aggregate fencer status across all events in a tournament.

    Returns:
        {
            "active": [FencerStatus, ...],
            "waiting": [FencerStatus, ...],
            "finished": [FencerStatus, ...],
        }
    """
```

**Status computation logic:**

For each event with club fencers:

1. **Pools Phase:**
   - Fetch pools bundle (pool HTML + results JSON)
   - Find club fencers in pool rosters
   - For each fencer:
     - If strip assigned and no result yet → `activity="active"`, `phase="pools"`
     - If no strip yet → `activity="waiting"`, `phase="pools"`
     - If result="Eliminated" → `activity="finished"`, `phase="pools"`, `result="Eliminated"`
     - If result="Advanced" → `activity="waiting"`, `phase="pools"`, `result="Advanced to DE"`

2. **DE Phase:**
   - Fetch DE tableau
   - Find club fencers in bracket
   - For each fencer:
     - Determine current round (find their latest match)
     - If match in_progress → `activity="active"`, `phase="de"`, `de_round="32"`
     - If match pending → `activity="waiting"`, `phase="de"`, `de_round="16"`
     - If match complete and no next match → `activity="finished"`, `phase="de"`, `result="Eliminated (Table of 32)"`
     - If in finals → special results: "Gold Medal", "Silver Medal", "Bronze Medal"

3. **Error Handling:**
   - If fetch fails for an event, include fencers with `error="Unable to fetch data"`
   - Continue processing other events
   - Log errors for debugging

### 2. Dashboard Route

Add to `app/main.py`:

```python
@app.get("/tournament/{tournament_id}/dashboard", response_class=HTMLResponse)
async def tournament_dashboard(
    tournament_id: int,
    request: Request,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Consolidated dashboard showing all club fencers across events.
    """
    # Verify tournament belongs to user
    tournament = db.query(TrackedTournament).filter(
        TrackedTournament.id == tournament_id,
        TrackedTournament.user_id == user.id,
    ).first()

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # Get all cached events
    events = tournament.events

    # Aggregate fencer status
    from app.services.tournament_service import get_tournament_fencer_status

    try:
        grouped_fencers = get_tournament_fencer_status(
            tournament_id=tournament.id,
            club_filter=tournament.club_filter,
            cached_events=events,
        )
    except Exception as e:
        # Show error page but don't crash
        return templates.TemplateResponse(
            "tournament_dashboard.html",
            {
                "request": request,
                "tournament": tournament,
                "error": f"Failed to fetch fencer data: {str(e)}",
                "grouped_fencers": {"active": [], "waiting": [], "finished": []},
            }
        )

    return templates.TemplateResponse(
        "tournament_dashboard.html",
        {
            "request": request,
            "tournament": tournament,
            "grouped_fencers": grouped_fencers,
            "last_updated": datetime.now(UTC).strftime("%I:%M %p"),
        }
    )
```

### 3. Dashboard Template

Create `app/templates/tournament_dashboard.html`:

```html
{% extends "base.html" %}

{% block title %}{{ tournament.tournament_name }} - Dashboard{% endblock %}

{% block content %}
<section>
    <header style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <div>
            <h1>{{ tournament.tournament_name }}</h1>
            <p>
                {% if tournament.club_filter %}{{ tournament.club_filter }}{% endif %}
                {% if tournament.weapon_filter %} · {{ tournament.weapon_filter }} events{% endif %}
            </p>
        </div>
        <div>
            <form method="get" action="/tournament/{{ tournament.id }}/dashboard" style="margin: 0;">
                <button type="submit" name="force_refresh" value="true">
                    🔄 Refresh
                </button>
            </form>
        </div>
    </header>

    {% if error %}
    <article class="error-message">
        <p>{{ error }}</p>
    </article>
    {% endif %}

    {% if last_updated %}
    <p><small>Last updated: {{ last_updated }}</small></p>
    {% endif %}

    <!-- ACTIVE NOW Section -->
    <section class="fencer-group">
        <h2>Active Now <span class="badge">{{ grouped_fencers.active|length }}</span></h2>
        {% if grouped_fencers.active %}
        <table>
            <thead>
                <tr>
                    <th>Fencer</th>
                    <th>Event</th>
                    <th>Location</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for fencer in grouped_fencers.active %}
                <tr class="fencer-active">
                    <td><strong>{{ fencer.name }}</strong></td>
                    <td>{{ fencer.event_name }}</td>
                    <td>
                        {% if fencer.strip %}Strip {{ fencer.strip }}{% endif %}
                        {% if fencer.pool_number %}Pool {{ fencer.pool_number }}{% endif %}
                        {% if fencer.de_round %}Table of {{ fencer.de_round }}{% endif %}
                    </td>
                    <td>
                        {% if fencer.phase == "pools" %}Fencing pools{% endif %}
                        {% if fencer.phase == "de" %}DE in progress{% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p>No fencers currently active.</p>
        {% endif %}
    </section>

    <!-- WAITING Section -->
    <section class="fencer-group">
        <h2>Waiting <span class="badge">{{ grouped_fencers.waiting|length }}</span></h2>
        {% if grouped_fencers.waiting %}
        <table>
            <thead>
                <tr>
                    <th>Fencer</th>
                    <th>Event</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for fencer in grouped_fencers.waiting %}
                <tr>
                    <td>{{ fencer.name }}</td>
                    <td>{{ fencer.event_name }}</td>
                    <td>
                        {% if fencer.result %}{{ fencer.result }}{% else %}Waiting to fence{% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p>No fencers waiting.</p>
        {% endif %}
    </section>

    <!-- FINISHED Section -->
    <section class="fencer-group">
        <h2>Finished <span class="badge">{{ grouped_fencers.finished|length }}</span></h2>
        {% if grouped_fencers.finished %}
        <table>
            <thead>
                <tr>
                    <th>Fencer</th>
                    <th>Event</th>
                    <th>Result</th>
                </tr>
            </thead>
            <tbody>
                {% for fencer in grouped_fencers.finished %}
                <tr>
                    <td>{{ fencer.name }}</td>
                    <td>{{ fencer.event_name }}</td>
                    <td>
                        <span class="result-badge">
                            {{ fencer.result or "Complete" }}
                        </span>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p>No fencers finished yet.</p>
        {% endif %}
    </section>

    <footer style="margin-top: 2rem; border-top: 1px solid var(--muted-border-color); padding-top: 1rem;">
        <a href="/tournament/{{ tournament.id }}">← View Events</a>
        <a href="/dashboard" style="margin-left: 1rem;">← All Tournaments</a>
    </footer>
</section>
{% endblock %}
```

### 4. Update Tournament Detail Page

Modify `app/templates/tournament_detail.html` to add dashboard link:

```html
<h1>{{ tournament.tournament_name }}</h1>
<p>
    {% if tournament.club_filter %}Club: {{ tournament.club_filter }}{% endif %}
    {% if tournament.weapon_filter %} · {{ tournament.weapon_filter }} only{% endif %}
</p>

<!-- ADD THIS -->
<div style="margin-bottom: 1rem;">
    <a href="/tournament/{{ tournament.id }}/dashboard" role="button">
        View Live Dashboard →
    </a>
</div>

<h2>Events ({{ tournament.events|length }})</h2>
```

### 5. Update Dashboard List

Modify `app/templates/dashboard.html` to link to consolidated dashboard:

```html
{% for t in tournaments %}
<li>
    <a href="/tournament/{{ t.id }}/dashboard">{{ t.tournament_name }}</a>
    <small>{{ t.events|length }} events · {{ t.club_filter or 'No club filter' }}</small>
</li>
{% endfor %}
```

### 6. CSS Enhancements

Add to `app/static/styles.css`:

```css
/* Fencer group sections */
.fencer-group {
    margin-bottom: 2rem;
}

.fencer-group h2 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.badge {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    background: var(--primary-focus);
    color: white;
    border-radius: 4px;
    font-size: 0.875rem;
    font-weight: normal;
}

/* Active fencer row highlighting */
.fencer-active {
    background: var(--primary-focus);
    font-weight: 600;
}

/* Result badges */
.result-badge {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    background: var(--secondary);
    color: white;
    border-radius: 4px;
    font-size: 0.875rem;
}
```

### 7. Tests

Create `tests/web/test_tournament_dashboard.py`:

```python
"""Tests for consolidated tournament dashboard."""
import pytest
from unittest.mock import patch
from tests.web.test_tournament import authenticated_client, test_db, _extract_csrf_token
from app.models import TrackedTournament, CachedEvent


def test_dashboard_requires_auth(client, test_db):
    """Dashboard requires authentication."""
    # Create tournament
    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="A" * 32,
        tournament_name="Test Tournament",
        tournament_url="https://example.com",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    tournament_id = tournament.id
    db.close()

    response = client.get(f"/tournament/{tournament_id}/dashboard")
    assert response.status_code == 401


def test_dashboard_renders(authenticated_client, test_db):
    """Dashboard renders with empty data."""
    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="A" * 32,
        tournament_name="Test Tournament",
        tournament_url="https://example.com",
        club_filter="Elite Fencers",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    tournament_id = tournament.id
    db.close()

    with patch("app.services.tournament_service.get_tournament_fencer_status", return_value={
        "active": [],
        "waiting": [],
        "finished": [],
    }):
        response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")

    assert response.status_code == 200
    assert "Test Tournament" in response.text
    assert "Active Now" in response.text
    assert "Waiting" in response.text
    assert "Finished" in response.text


def test_dashboard_shows_active_fencers(authenticated_client, test_db):
    """Dashboard displays active fencers."""
    from app.services.tournament_service import FencerStatus

    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="A" * 32,
        tournament_name="Test Tournament",
        tournament_url="https://example.com",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    tournament_id = tournament.id
    db.close()

    active_fencer = FencerStatus(
        name="Jane Smith",
        event_id="B" * 32,
        event_name="Women's Epee",
        weapon="Epee",
        strip="A5",
        pool_number=3,
        activity="active",
        phase="pools",
    )

    with patch("app.services.tournament_service.get_tournament_fencer_status", return_value={
        "active": [active_fencer],
        "waiting": [],
        "finished": [],
    }):
        response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")

    assert response.status_code == 200
    assert "Jane Smith" in response.text
    assert "Women" in response.text and "Epee" in response.text
    assert "Strip A5" in response.text
    assert "Pool 3" in response.text


def test_dashboard_shows_finished_fencers(authenticated_client, test_db):
    """Dashboard displays finished fencers with results."""
    from app.services.tournament_service import FencerStatus

    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="A" * 32,
        tournament_name="Test Tournament",
        tournament_url="https://example.com",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    tournament_id = tournament.id
    db.close()

    finished_fencer = FencerStatus(
        name="Bob Johnson",
        event_id="B" * 32,
        event_name="Men's Foil",
        weapon="Foil",
        activity="finished",
        phase="de",
        result="Eliminated (Table of 32)",
    )

    with patch("app.services.tournament_service.get_tournament_fencer_status", return_value={
        "active": [],
        "waiting": [],
        "finished": [finished_fencer],
    }):
        response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")

    assert response.status_code == 200
    assert "Bob Johnson" in response.text
    assert "Eliminated" in response.text


def test_dashboard_force_refresh(authenticated_client, test_db):
    """Dashboard accepts force_refresh parameter."""
    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="A" * 32,
        tournament_name="Test Tournament",
        tournament_url="https://example.com",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    tournament_id = tournament.id
    db.close()

    with patch("app.services.tournament_service.get_tournament_fencer_status", return_value={
        "active": [],
        "waiting": [],
        "finished": [],
    }):
        response = authenticated_client.get(
            f"/tournament/{tournament_id}/dashboard?force_refresh=true"
        )

    assert response.status_code == 200


def test_dashboard_handles_errors(authenticated_client, test_db):
    """Dashboard shows error message when fetch fails."""
    _, SessionLocal = test_db
    db = SessionLocal()
    tournament = TrackedTournament(
        user_id=1,
        tournament_id="A" * 32,
        tournament_name="Test Tournament",
        tournament_url="https://example.com",
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    tournament_id = tournament.id
    db.close()

    with patch(
        "app.services.tournament_service.get_tournament_fencer_status",
        side_effect=Exception("Network error")
    ):
        response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")

    assert response.status_code == 200
    assert "Failed to fetch" in response.text or "Network error" in response.text
```

Add unit tests for `tests/services/test_tournament_service.py`:
- test_get_tournament_fencer_status_empty
- test_pools_active_fencer
- test_pools_waiting_fencer
- test_pools_eliminated_fencer
- test_de_active_fencer
- test_de_finished_fencer
- test_handles_fetch_errors

## Implementation Notes

### Status Determination Algorithm

**Pools Phase:**
1. Fetch pools bundle for event
2. Match fencers by club (case-insensitive substring)
3. Check pool roster for fencer name
4. Check if strip assigned in pool HTML
5. Check results JSON for advancement status

**DE Phase:**
1. Fetch DE tableau for event
2. Find fencer in bracket by name
3. Determine current round from matches
4. Check match status (pending, in_progress, complete)
5. Compute placement from final rounds

### Club Matching

Reuse existing logic from Phase C:
```python
def match_club(fencer: dict, club_filter: str) -> bool:
    """Check if fencer matches club filter."""
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

### Caching Strategy

- Use existing FTL client cache (180s TTL)
- `force_refresh=true` bypasses cache
- Don't cache aggregated status (compute fresh each time)

### Error Handling

- Continue processing other events if one fails
- Show partial data with error indicators
- Log errors to console for debugging
- Don't crash dashboard on fetch failures

## Acceptance Criteria

- [ ] `/tournament/{id}/dashboard` requires authentication
- [ ] Dashboard shows fencers grouped by activity (active, waiting, finished)
- [ ] Active fencers show current location (strip, pool, DE round)
- [ ] Finished fencers show result (eliminated, placement)
- [ ] Refresh button refetches latest data
- [ ] Dashboard handles fetch errors gracefully
- [ ] Links to tournament detail page work
- [ ] CSS styling matches Pico CSS theme
- [ ] All web tests pass (5+ new tests)
- [ ] All service unit tests pass (7+ new tests)
- [ ] No regressions to existing functionality

## Open Questions

1. **Name matching:** How to handle fencers with same name across events?
   - **Answer:** Include event name in display, assume same name = same person

2. **Multiple clubs:** What if fencer has club1="Elite Fencers" and club2="Other Club"?
   - **Answer:** Match on either club1 or club2

3. **Event phase detection:** How to know if event is in pools vs DE?
   - **Answer:** Try fetching pools first; if no data, try DE; if both exist, show both

4. **Performance:** What if tournament has 20 events?
   - **Answer:** Use cache (180s TTL); sequential fetching acceptable for MVP

## Timeline Estimate

- Service layer (orchestration): 2-3 hours
- Dashboard route + template: 2-3 hours
- CSS styling: 1 hour
- Tests (web + service): 2-3 hours
- **Total:** 1 day for experienced developer

---

*Ready for Phase D implementation.*
