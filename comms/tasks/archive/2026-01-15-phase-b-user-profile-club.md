# Task: Phase B — User Profile & Club Setting

**Date:** 2026-01-15
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Add a `club` field to the User model and create a profile page where users can view and edit their profile information, including their home club. This is foundational for the club-based auto-tracking feature.

## User Stories

- As a user, I can set my home club so the app can automatically track my clubmates at tournaments.
- As a user, I can view and edit my profile (username, email, club).
- As a user, I can change my club at any time.

## Scope (In)

- Add `club` column to User model (nullable string)
- Create `/profile` page (GET: view, POST: update)
- Add "Profile" link to navigation
- Optional: Add club field to registration form

## Scope (Out)

- Club validation against a list (free-form text for now)
- Club search/autocomplete
- Multiple clubs per user

## Deliverables

### 1. Database Model Update

Modify `app/models.py`:

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    club = Column(String(200), nullable=True)  # NEW
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

### 2. Database Migration

Since we're using SQLite in development, the simplest approach:

**Option A (Recommended for dev):** Add column directly with ALTER TABLE
```sql
ALTER TABLE users ADD COLUMN club VARCHAR(200);
```

**Option B:** Use Alembic migration (if set up)

For now, handle gracefully if column doesn't exist (SQLAlchemy will add it on next `create_all`).

### 3. Profile Page Routes

Add to `app/main.py`:

**GET /profile** - Render profile form with current values
- Requires authentication
- Shows: username, email, club
- Pre-populates form with current values

**POST /profile** - Update profile
- Requires authentication + CSRF
- Validates inputs
- Updates user record
- Shows success message

### 4. Template

Create `app/templates/profile.html`:

```html
{% extends "base.html" %}
{% block title %}Profile{% endblock %}
{% block content %}
<section>
    <h1>Your Profile</h1>

    {% if success %}
    <article class="info">
        <p>Profile updated successfully.</p>
    </article>
    {% endif %}

    {% if error %}
    <article class="error-message">
        <p>{{ error }}</p>
    </article>
    {% endif %}

    <form method="post" action="/profile">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

        <label>
            Username
            <input type="text" name="username" value="{{ user.username }}"
                   required minlength="3" maxlength="50">
        </label>

        <label>
            Email
            <input type="email" name="email" value="{{ user.email }}" required>
        </label>

        <label>
            Home Club
            <input type="text" name="club" value="{{ user.club or '' }}"
                   placeholder="e.g., Elite Fencers Club" maxlength="200">
            <small>Used for automatic fencer tracking at tournaments</small>
        </label>

        <button type="submit">Save Changes</button>
    </form>
</section>
{% endblock %}
```

### 5. Navigation Update

Update `app/templates/base.html` to add Profile link:

```html
<li><a href="/profile">Profile</a></li>
```

Place after "Dashboard" in the authenticated user nav.

### 6. CRUD Helper (Optional)

Add to `app/crud.py`:

```python
def update_user_profile(db: Session, user_id: int, username: str, email: str, club: str | None) -> User:
    """Update user profile fields."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.username = username
        user.email = email
        user.club = club
        db.commit()
        db.refresh(user)
    return user
```

### 7. Tests

Add `tests/web/test_profile.py`:

```python
def test_profile_requires_auth(client):
    """GET /profile returns 401 without auth."""
    response = client.get("/profile")
    assert response.status_code == 401

def test_profile_renders(authenticated_client):
    """GET /profile renders for authenticated user."""
    response = authenticated_client.get("/profile")
    assert response.status_code == 200
    assert "Your Profile" in response.text
    assert "testuser" in response.text  # username from fixture

def test_profile_update_club(authenticated_client):
    """POST /profile updates club field."""
    csrf_token = _get_csrf_token(authenticated_client, "/profile")
    response = authenticated_client.post("/profile", data={
        "csrf_token": csrf_token,
        "username": "testuser",
        "email": "test@example.com",
        "club": "Elite Fencers Club",
    })
    assert response.status_code == 200
    assert "updated successfully" in response.text
    assert "Elite Fencers Club" in response.text

def test_profile_update_username(authenticated_client):
    """POST /profile can update username."""
    csrf_token = _get_csrf_token(authenticated_client, "/profile")
    response = authenticated_client.post("/profile", data={
        "csrf_token": csrf_token,
        "username": "newusername",
        "email": "test@example.com",
        "club": "",
    })
    assert response.status_code == 200
    assert "newusername" in response.text

def test_profile_validates_empty_username(authenticated_client):
    """POST /profile rejects empty username."""
    csrf_token = _get_csrf_token(authenticated_client, "/profile")
    response = authenticated_client.post("/profile", data={
        "csrf_token": csrf_token,
        "username": "",
        "email": "test@example.com",
        "club": "",
    })
    assert response.status_code == 200
    assert "required" in response.text.lower() or "error" in response.text.lower()

def test_profile_validates_duplicate_username(authenticated_client, test_db):
    """POST /profile rejects duplicate username."""
    # Create another user first
    # ... (setup second user)
    # Try to change to that username
    # Assert error

def test_profile_requires_csrf(authenticated_client):
    """POST /profile requires CSRF token."""
    response = authenticated_client.post("/profile", data={
        "username": "testuser",
        "email": "test@example.com",
        "club": "Test Club",
    })
    assert response.status_code == 403

def test_profile_club_optional(authenticated_client):
    """Club field can be empty."""
    csrf_token = _get_csrf_token(authenticated_client, "/profile")
    response = authenticated_client.post("/profile", data={
        "csrf_token": csrf_token,
        "username": "testuser",
        "email": "test@example.com",
        "club": "",
    })
    assert response.status_code == 200
    assert "updated successfully" in response.text
```

## Implementation Notes

- **Validation:** Username 3-50 chars, email valid format, club max 200 chars
- **Uniqueness:** Check username/email not taken by another user on update
- **Club format:** Free-form text, no validation against club list
- **Empty club:** Treat empty string as NULL in database
- **Success feedback:** Show confirmation message after successful update
- **Error handling:** Show field-specific errors inline

## Acceptance Criteria

- [ ] `club` column exists in users table
- [ ] `/profile` renders for authenticated users, 401 for unauthenticated
- [ ] User can view their current username, email, and club
- [ ] User can update their club (including clearing it)
- [ ] User can update their username and email
- [ ] Duplicate username/email rejected with clear error
- [ ] "Profile" link appears in navigation for logged-in users
- [ ] All tests pass
- [ ] No regressions to existing functionality
