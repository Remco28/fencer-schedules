# Task: Phase E — Manual Fencer Tracking

**Date:** 2026-01-16
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Allow users to manually add fencers to track beyond their club's auto-discovered members. This enables tracking teammates from affiliated clubs, friends from other clubs, or any fencer of interest.

The feature includes:
1. Cross-event fencer search within a tournament
2. Add/remove tracked fencers UI
3. Visual distinction between club (auto) and manual fencers on dashboard

## User Stories

- As a user, I can search for any fencer across all events in my tournament.
- As a user, I can add a fencer to my tracking list from search results.
- As a user, I can see which fencers were auto-discovered vs manually added.
- As a user, I can remove a manually-added fencer from my tracking list.
- As a user, I see both club and manual fencers on my consolidated dashboard.

## Scope (In)

- TrackedFencer model (stores manually tracked fencers)
- Fencer search within tournament context
- Add fencer button in search results
- Remove fencer action on dashboard
- Visual indicator for manual vs club fencers
- Update dashboard to include manual fencers

## Scope (Out)

- Tracking fencers across multiple tournaments
- Fencer favorites / permanent tracking list
- Push notifications for specific fencers
- Historical tracking data

## Dependencies

All these are already implemented:
- `fetch_pools_bundle()` and `fetch_competitors_json()` from `app/ftl/client.py`
- `get_tournament_fencer_status()` from `app/services/tournament_service.py`
- TrackedTournament and CachedEvent models
- Consolidated dashboard template

## Deliverables

### 1. TrackedFencer Model

Add to `app/models.py`:

```python
class TrackedFencer(Base):
    __tablename__ = "tracked_fencers"

    id = Column(Integer, primary_key=True, index=True)
    tracked_tournament_id = Column(
        Integer, ForeignKey("tracked_tournaments.id"), nullable=False, index=True
    )
    fencer_name = Column(String(200), nullable=False)
    source = Column(String(20), nullable=False, default="manual")  # "club" or "manual"
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    tournament = relationship("TrackedTournament", back_populates="tracked_fencers")
```

Update `TrackedTournament` to add the relationship:

```python
class TrackedTournament(Base):
    # ... existing fields ...

    tracked_fencers = relationship(
        "TrackedFencer",
        back_populates="tournament",
        cascade="all, delete-orphan",
    )
```

### 2. CRUD Operations

Add to `app/crud.py`:

```python
def add_tracked_fencer(
    db: Session,
    tournament_id: int,
    fencer_name: str,
    source: str = "manual",
) -> models.TrackedFencer:
    """Add a fencer to tracking list."""
    fencer = models.TrackedFencer(
        tracked_tournament_id=tournament_id,
        fencer_name=fencer_name.strip(),
        source=source,
    )
    db.add(fencer)
    db.flush()
    return fencer


def remove_tracked_fencer(db: Session, fencer_id: int, tournament_id: int) -> bool:
    """Remove a tracked fencer. Returns True if deleted."""
    fencer = (
        db.query(models.TrackedFencer)
        .filter(
            models.TrackedFencer.id == fencer_id,
            models.TrackedFencer.tracked_tournament_id == tournament_id,
        )
        .first()
    )
    if fencer:
        db.delete(fencer)
        db.flush()
        return True
    return False


def get_tracked_fencers(db: Session, tournament_id: int) -> list[models.TrackedFencer]:
    """Get all tracked fencers for a tournament."""
    return (
        db.query(models.TrackedFencer)
        .filter(models.TrackedFencer.tracked_tournament_id == tournament_id)
        .order_by(models.TrackedFencer.fencer_name)
        .all()
    )


def is_fencer_tracked(db: Session, tournament_id: int, fencer_name: str) -> bool:
    """Check if a fencer is already tracked."""
    return (
        db.query(models.TrackedFencer)
        .filter(
            models.TrackedFencer.tracked_tournament_id == tournament_id,
            models.TrackedFencer.fencer_name == fencer_name.strip(),
        )
        .first()
    ) is not None
```

### 3. Tournament Fencer Search

Add search functionality to `app/services/tournament_service.py`:

```python
def search_tournament_fencers(
    tournament_id: int,
    cached_events: list,
    query: str,
    force_refresh: bool = False,
) -> list[dict]:
    """
    Search for fencers across all events in a tournament.

    Args:
        tournament_id: The tournament DB ID
        cached_events: List of CachedEvent objects
        query: Search string (case-insensitive substring match)
        force_refresh: Bypass cache

    Returns:
        List of fencer dicts with keys: name, event_id, event_name, club, status
    """
    if not query or len(query) < 2:
        return []

    query_lower = query.lower().strip()
    results = []
    seen = set()  # Deduplicate by (name, event_id)

    for event in cached_events:
        # Try competitors JSON first (has full roster)
        try:
            competitors = fetch_competitors_json(
                event.event_id,
                force_refresh=force_refresh,
            )
            for comp in competitors:
                name = comp.get("name", "")
                if query_lower in name.lower():
                    key = (name, event.event_id)
                    if key not in seen:
                        seen.add(key)
                        results.append({
                            "name": name,
                            "event_id": event.event_id,
                            "event_name": event.event_name,
                            "club": comp.get("club1") or comp.get("clubs") or "",
                            "status": "registered",
                        })
        except Exception:
            # Fall back to pools bundle if competitors fails
            if event.pool_round_id:
                try:
                    bundle = fetch_pools_bundle(
                        event.event_id,
                        event.pool_round_id,
                        force_refresh=force_refresh,
                    )
                    for pool in bundle.get("pools", []):
                        for fencer in pool.get("fencers", []):
                            name = fencer.get("name", "")
                            if query_lower in name.lower():
                                key = (name, event.event_id)
                                if key not in seen:
                                    seen.add(key)
                                    results.append({
                                        "name": name,
                                        "event_id": event.event_id,
                                        "event_name": event.event_name,
                                        "club": fencer.get("club") or "",
                                        "status": "in_pools",
                                    })
                except Exception:
                    pass

    # Sort by name
    results.sort(key=lambda x: x["name"].lower())
    return results
```

### 4. Search Route

Add to `app/main.py`:

```python
@app.get("/tournament/{tournament_id}/search", response_class=HTMLResponse)
def tournament_search_page(
    tournament_id: int,
    request: Request,
    q: str = "",
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    """Search for fencers within a tournament."""
    tournament = (
        db.query(TrackedTournament)
        .options(selectinload(TrackedTournament.events))
        .filter(
            TrackedTournament.id == tournament_id,
            TrackedTournament.user_id == user.id,
        )
        .first()
    )

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    results = []
    error = None

    if q and len(q) >= 2:
        try:
            results = search_tournament_fencers(
                tournament_id=tournament.id,
                cached_events=tournament.events,
                query=q,
            )
            # Mark which fencers are already tracked
            tracked_names = {
                f.fencer_name for f in crud.get_tracked_fencers(db, tournament.id)
            }
            for r in results:
                r["is_tracked"] = r["name"] in tracked_names
        except Exception as exc:
            error = f"Search failed: {exc}"

    return dependencies.templates.TemplateResponse(
        request,
        "tournament_search.html",
        {
            "user": user,
            "tournament": tournament,
            "query": q,
            "results": results,
            "error": error,
        },
    )


@app.post("/tournament/{tournament_id}/track")
async def add_tracked_fencer(
    tournament_id: int,
    request: Request,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Add a fencer to tracking list."""
    tournament = (
        db.query(TrackedTournament)
        .filter(
            TrackedTournament.id == tournament_id,
            TrackedTournament.user_id == user.id,
        )
        .first()
    )

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    form = await request.form()
    fencer_name = (form.get("fencer_name") or "").strip()

    if not fencer_name:
        return RedirectResponse(
            url=f"/tournament/{tournament_id}/search",
            status_code=303,
        )

    # Check if already tracked
    if not crud.is_fencer_tracked(db, tournament.id, fencer_name):
        crud.add_tracked_fencer(db, tournament.id, fencer_name, source="manual")
        db.commit()

    # Redirect back to search with same query
    redirect_url = form.get("redirect_url") or f"/tournament/{tournament_id}/dashboard"
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/tournament/{tournament_id}/untrack/{fencer_id}")
def remove_tracked_fencer(
    tournament_id: int,
    fencer_id: int,
    user: User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(dependencies.validate_csrf),
):
    """Remove a fencer from tracking list."""
    tournament = (
        db.query(TrackedTournament)
        .filter(
            TrackedTournament.id == tournament_id,
            TrackedTournament.user_id == user.id,
        )
        .first()
    )

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    crud.remove_tracked_fencer(db, fencer_id, tournament.id)
    db.commit()

    return RedirectResponse(
        url=f"/tournament/{tournament_id}/dashboard",
        status_code=303,
    )
```

### 5. Search Template

Create `app/templates/tournament_search.html`:

```html
{% extends "base.html" %}

{% block title %}Search Fencers - {{ tournament.tournament_name }}{% endblock %}

{% block content %}
<section>
    <header class="dashboard-header">
        <div>
            <h1>Search Fencers</h1>
            <p>{{ tournament.tournament_name }}</p>
        </div>
        <a href="/tournament/{{ tournament.id }}/dashboard">Back to Dashboard</a>
    </header>

    {% if error %}
    <article class="error-message"><p>{{ error }}</p></article>
    {% endif %}

    <form method="get" action="/tournament/{{ tournament.id }}/search" class="search-form">
        <label>
            Fencer Name
            <input type="text" name="q" value="{{ query or '' }}"
                   placeholder="Enter at least 2 characters"
                   minlength="2" autofocus>
        </label>
        <button type="submit">Search</button>
    </form>

    {% if query and results %}
    <h2>Results ({{ results|length }})</h2>
    <table>
        <thead>
            <tr>
                <th>Name</th>
                <th>Event</th>
                <th>Club</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            {% for fencer in results %}
            <tr>
                <td>{{ fencer.name }}</td>
                <td>{{ fencer.event_name }}</td>
                <td>{{ fencer.club or '—' }}</td>
                <td>
                    {% if fencer.is_tracked %}
                    <span class="tracked-badge">Tracking</span>
                    {% else %}
                    <form method="post" action="/tournament/{{ tournament.id }}/track" class="inline-form">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                        <input type="hidden" name="fencer_name" value="{{ fencer.name }}">
                        <input type="hidden" name="redirect_url" value="/tournament/{{ tournament.id }}/search?q={{ query }}">
                        <button type="submit" class="small">+ Track</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% elif query %}
    <p>No fencers found matching "{{ query }}".</p>
    {% endif %}
</section>
{% endblock %}
```

### 6. Update Dashboard Template

Modify `app/templates/tournament_dashboard.html`:

**Add "Add Fencer" link in header:**
```html
<header class="dashboard-header">
    <div>
        <h1>{{ tournament.tournament_name }}</h1>
        <p>
            {% if tournament.club_filter %}{{ tournament.club_filter }}{% endif %}
            {% if tournament.weapon_filter %} · {{ tournament.weapon_filter }} events{% endif %}
        </p>
    </div>
    <div>
        <a href="/tournament/{{ tournament.id }}/search" class="btn small outline">+ Add Fencer</a>
        <form method="get" action="/tournament/{{ tournament.id }}/dashboard" class="inline-form">
            <button type="submit" name="force_refresh" value="true">Refresh</button>
        </form>
    </div>
</header>
```

**Add source indicator to fencer rows:**
```html
<tr class="{% if fencer.activity == 'active' %}fencer-active{% endif %}">
    <td>
        <strong>{{ fencer.name }}</strong>
        {% if fencer.source == 'manual' %}
        <span class="source-badge manual">manual</span>
        {% endif %}
    </td>
    <!-- ... rest of row ... -->
</tr>
```

**Add remove button for manual fencers in waiting/finished sections:**
```html
<td>
    {{ fencer.name }}
    {% if fencer.source == 'manual' %}
    <span class="source-badge manual">manual</span>
    <form method="post" action="/tournament/{{ tournament.id }}/untrack/{{ fencer.id }}"
          class="inline-form" style="display: inline;">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit" class="small outline danger"
                onclick="return confirm('Stop tracking {{ fencer.name }}?')">×</button>
    </form>
    {% endif %}
</td>
```

### 7. Update Tournament Service

Modify `app/services/tournament_service.py` to include manual fencers:

```python
def get_tournament_fencer_status(
    tournament_id: int,
    club_filter: str,
    cached_events: list,
    tracked_fencers: list = None,  # NEW: list of TrackedFencer objects
    force_refresh: bool = False,
) -> dict[str, list[FencerStatus]]:
    """
    Aggregate fencer status across all events in a tournament.

    Now includes both:
    - Club fencers (auto-discovered from club_filter)
    - Manual fencers (from tracked_fencers list)
    """
    # ... existing logic ...

    # Build set of names to track (club filter + manual)
    manual_names = set()
    if tracked_fencers:
        manual_names = {f.fencer_name for f in tracked_fencers if f.source == "manual"}

    # When matching fencers, also check if name in manual_names
    # Add 'source' field to FencerStatus
```

Update `FencerStatus` dataclass:
```python
@dataclass
class FencerStatus:
    # ... existing fields ...
    source: str = "club"  # "club" or "manual"
    fencer_db_id: Optional[int] = None  # TrackedFencer.id for manual fencers
```

### 8. Update Dashboard Route

Modify the dashboard route in `app/main.py` to pass tracked fencers:

```python
@app.get("/tournament/{tournament_id}/dashboard", response_class=HTMLResponse)
def tournament_dashboard(
    tournament_id: int,
    request: Request,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(dependencies.get_current_user),
):
    tournament = (
        db.query(TrackedTournament)
        .options(
            selectinload(TrackedTournament.events),
            selectinload(TrackedTournament.tracked_fencers),  # NEW
        )
        .filter(
            TrackedTournament.id == tournament_id,
            TrackedTournament.user_id == user.id,
        )
        .first()
    )

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    try:
        grouped_fencers = get_tournament_fencer_status(
            tournament_id=tournament.id,
            club_filter=tournament.club_filter or "",
            cached_events=tournament.events,
            tracked_fencers=tournament.tracked_fencers,  # NEW
            force_refresh=force_refresh,
        )
    except Exception as exc:
        # ... error handling ...
```

### 9. CSS Additions

Add to `app/static/styles.css`:

```css
/* Source badges */
.source-badge {
    display: inline-block;
    padding: 0.125rem 0.375rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: normal;
    margin-left: 0.5rem;
    vertical-align: middle;
}

.source-badge.manual {
    background: #6c757d;
    color: #ffffff;
}

/* Tracked badge in search results */
.tracked-badge {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    background: #27ae60;
    color: #ffffff;
    border-radius: 4px;
    font-size: 0.75rem;
}

/* Search form */
.search-form {
    display: flex;
    gap: 1rem;
    align-items: flex-end;
    margin-bottom: 1.5rem;
}

.search-form label {
    flex: 1;
    margin: 0;
}

.search-form button {
    margin: 0;
    height: fit-content;
}

/* Danger button */
.danger {
    background: transparent;
    border-color: #c0392b;
    color: #c0392b;
}

.danger:hover {
    background: #c0392b;
    color: #ffffff;
}
```

### 10. Tests

Create `tests/web/test_tracked_fencers.py`:

```python
"""Tests for manual fencer tracking."""
import pytest
from unittest.mock import patch

from app.models import TrackedTournament, TrackedFencer
from app.services import rate_limit_service
from tests.web.test_tournament import authenticated_client, client, test_db


@pytest.fixture(autouse=True)
def clear_rate_limits():
    rate_limit_service._rate_limits.clear()
    yield
    rate_limit_service._rate_limits.clear()


def _create_tournament(session_factory, user_id=1):
    db = session_factory()
    tournament = TrackedTournament(
        user_id=user_id,
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
    return tournament_id


def test_search_page_requires_auth(client, test_db):
    """Search page requires authentication."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)
    response = client.get(f"/tournament/{tournament_id}/search")
    assert response.status_code == 401


def test_search_page_renders(authenticated_client, test_db):
    """Search page renders for authenticated users."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)
    response = authenticated_client.get(f"/tournament/{tournament_id}/search")
    assert response.status_code == 200
    assert "Search Fencers" in response.text


def test_search_with_query(authenticated_client, test_db):
    """Search returns results for valid query."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    with patch("app.main.search_tournament_fencers", return_value=[
        {"name": "John Smith", "event_id": "B" * 32, "event_name": "Men's Epee", "club": "Other Club", "is_tracked": False},
    ]):
        response = authenticated_client.get(f"/tournament/{tournament_id}/search?q=Smith")

    assert response.status_code == 200
    assert "John Smith" in response.text
    assert "Men" in response.text


def test_add_tracked_fencer(authenticated_client, test_db):
    """Can add a fencer to tracking list."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    # Get CSRF token
    response = authenticated_client.get(f"/tournament/{tournament_id}/search")
    csrf_token = _extract_csrf(response.text)

    response = authenticated_client.post(
        f"/tournament/{tournament_id}/track",
        data={
            "csrf_token": csrf_token,
            "fencer_name": "Jane Doe",
            "redirect_url": f"/tournament/{tournament_id}/dashboard",
        },
    )

    assert response.status_code == 303

    # Verify fencer was added
    db = SessionLocal()
    fencer = db.query(TrackedFencer).filter(
        TrackedFencer.tracked_tournament_id == tournament_id,
        TrackedFencer.fencer_name == "Jane Doe",
    ).first()
    assert fencer is not None
    assert fencer.source == "manual"
    db.close()


def test_remove_tracked_fencer(authenticated_client, test_db):
    """Can remove a tracked fencer."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    # Add a fencer first
    db = SessionLocal()
    fencer = TrackedFencer(
        tracked_tournament_id=tournament_id,
        fencer_name="Jane Doe",
        source="manual",
    )
    db.add(fencer)
    db.commit()
    fencer_id = fencer.id
    db.close()

    # Get CSRF token
    response = authenticated_client.get(f"/tournament/{tournament_id}/dashboard")
    csrf_token = _extract_csrf(response.text)

    response = authenticated_client.post(
        f"/tournament/{tournament_id}/untrack/{fencer_id}",
        data={"csrf_token": csrf_token},
    )

    assert response.status_code == 303

    # Verify fencer was removed
    db = SessionLocal()
    fencer = db.query(TrackedFencer).filter(TrackedFencer.id == fencer_id).first()
    assert fencer is None
    db.close()


def test_cannot_add_duplicate_fencer(authenticated_client, test_db):
    """Adding same fencer twice doesn't create duplicate."""
    _, SessionLocal = test_db
    tournament_id = _create_tournament(SessionLocal)

    # Add fencer first
    db = SessionLocal()
    fencer = TrackedFencer(
        tracked_tournament_id=tournament_id,
        fencer_name="Jane Doe",
        source="manual",
    )
    db.add(fencer)
    db.commit()
    db.close()

    # Get CSRF token
    response = authenticated_client.get(f"/tournament/{tournament_id}/search")
    csrf_token = _extract_csrf(response.text)

    # Try to add again
    response = authenticated_client.post(
        f"/tournament/{tournament_id}/track",
        data={
            "csrf_token": csrf_token,
            "fencer_name": "Jane Doe",
        },
    )

    assert response.status_code == 303

    # Verify only one fencer exists
    db = SessionLocal()
    count = db.query(TrackedFencer).filter(
        TrackedFencer.tracked_tournament_id == tournament_id,
        TrackedFencer.fencer_name == "Jane Doe",
    ).count()
    assert count == 1
    db.close()


def _extract_csrf(html: str) -> str:
    """Extract CSRF token from HTML."""
    import re
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ""
```

Add service tests to `tests/services/test_tournament_service.py`:

```python
def test_search_tournament_fencers_empty_query():
    """Empty query returns empty results."""
    result = search_tournament_fencers(1, [], "", False)
    assert result == []


def test_search_tournament_fencers_short_query():
    """Query under 2 chars returns empty results."""
    result = search_tournament_fencers(1, [], "A", False)
    assert result == []
```

## Implementation Notes

### Name Matching for Manual Fencers

When checking if a manual fencer should appear in results:
1. Exact match on `fencer_name` field
2. Search across all events in tournament
3. If found in any event, include in dashboard with that event's context

### Deduplication

A fencer might appear in multiple events. The dashboard should:
- Show one row per (fencer, event) combination
- A manually tracked fencer in 2 events appears twice

### Source Priority

If a fencer matches BOTH club filter and manual tracking:
- Mark as "club" source (auto-discovered takes priority)
- Don't show duplicate entry

### Performance

- Search fetches competitors JSON for each event (cached)
- Manual fencer tracking is stored in DB
- Dashboard query uses eager loading for tracked_fencers

## Acceptance Criteria

- [ ] TrackedFencer model exists with proper relationships
- [ ] `/tournament/{id}/search` page renders and searches work
- [ ] Can add a fencer to tracking list from search results
- [ ] Can remove a manually-tracked fencer from dashboard
- [ ] Dashboard shows both club and manual fencers
- [ ] Manual fencers have visual indicator (badge)
- [ ] Duplicate fencer tracking is prevented
- [ ] CSRF protection on all POST endpoints
- [ ] All new tests pass (8+ tests)
- [ ] No regressions to existing functionality

## Files to Create/Modify

**Create:**
- `app/templates/tournament_search.html`
- `tests/web/test_tracked_fencers.py`

**Modify:**
- `app/models.py` (add TrackedFencer)
- `app/crud.py` (add fencer tracking CRUD)
- `app/main.py` (add search/track/untrack routes)
- `app/services/tournament_service.py` (add search function, update status function)
- `app/templates/tournament_dashboard.html` (add source badges, remove buttons)
- `app/static/styles.css` (add new styles)

---

*Ready for Phase E implementation.*
