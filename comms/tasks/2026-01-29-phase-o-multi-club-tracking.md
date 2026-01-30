# Task: Phase O - Multi-Club Tracking

**Goal:** Allow users to track multiple clubs per tournament (e.g., "ELITE FC" AND "Medeo") and provide an interface to easily select clubs from the list of actual tournament participants.

**Context:**
Currently, users can only track a single club string. FencingTimeLive often uses inconsistent club names (abbreviations vs full names). Users need to be able to select multiple variations or completely different clubs to track friends/rivals.

**Branch:** `feature/multi-club-tracking`

---

## 1. Database Changes (`app/models.py`)

### A. New Model: `TournamentClub`
Create a new table to store the many-to-one relationship between a tournament and tracked clubs.

```python
class TournamentClub(Base):
    __tablename__ = "tournament_clubs"

    id = Column(Integer, primary_key=True, index=True)
    tracked_tournament_id = Column(Integer, ForeignKey("tracked_tournaments.id"))
    club_name = Column(String, index=True)
    
    # Relationship
    tournament = relationship("TrackedTournament", back_populates="clubs")
```

### B. Update `TrackedTournament`
- Add the relationship: `clubs = relationship("TournamentClub", back_populates="tournament", cascade="all, delete-orphan")`.
- **Note:** Keep the old `club_filter` column for now as a fallback/legacy field, but primarily use the `clubs` relationship.

---

## 2. Business Logic (`app/services/`)

### A. Update `club_matcher.py`
Modify `match_club` to accept a list of club names.

```python
def match_club(fencer: dict, club_filters: list[str] | str) -> bool:
    # If string, convert to list (legacy support)
    # Iterate through club_filters
    # Return True if ANY match
```

### B. Update `tournament_service.py`
Update `get_tournament_fencer_status` to pull the list of clubs from `tournament.clubs` (list of `TournamentClub` objects) and pass that list to `match_club`.

### C. Migration Logic (`app/main.py` -> `on_startup` or manual)
We need a way to migrate existing `club_filter` strings to the new table.
- Create a helper `migrate_legacy_clubs(db)`:
    - Query all `TrackedTournament`.
    - If `club_filter` is set and `clubs` is empty:
        - Create `TournamentClub(club_name=t.club_filter)`.
        - Add to DB.

---

## 3. UI Implementation (`app/templates/`)

### A. New Route: `GET /tournament/{id}/edit`
- **Controller:** `app/main.py`
- **Logic:**
    1. Fetch `TrackedTournament`.
    2. **Smart Discovery:** Fetch `competitors_json` from FTL for one of the events (any event in the tournament) to get a list of *all participating clubs*.
    3. Extract unique `club1` and `club2` names from competitors.
    4. Render `tournament_edit.html` with:
        - `tournament`: The DB object.
        - `tracked_clubs`: List of currently tracked clubs.
        - `available_clubs`: List of all discovered clubs from FTL (for suggestions).

### B. New Template: `tournament_edit.html`
- **Form:**
    - List currently tracked clubs as "tags" with an "X" to remove.
    - Input field to add a new club.
    - **"Available Clubs" Section:** A list of badges/buttons. Clicking one adds it to the tracked list.
    - "Save" button.

### C. Route: `POST /tournament/{id}/edit`
- **Logic:**
    - Receive list of club names.
    - Clear existing `TournamentClub` entries for this tournament.
    - Insert new `TournamentClub` entries.
    - **Crucial:** Trigger a re-calculation or cache refresh (since the tracked fencer list has changed). calling `_build_tournament_events` (or similar logic) to update `fencer_count` on events is a good idea.

---

## 4. Execution Steps

1.  **Models:** Add `TournamentClub` and relationships.
2.  **Migration:** Add startup migration logic to `init_db` or `main.py` to ensure existing users don't lose their tracking.
3.  **Service:** Update `club_matcher` to handle multiple clubs.
4.  **Edit Page:** Implement the GET/POST routes and the `tournament_edit.html` template.
5.  **Refine Dashboard:** Ensure dashboard logic uses the new list.

---

## 5. Success Criteria

1.  User can click "Edit" on a tournament.
2.  User sees list of *actual* clubs from FTL.
3.  User can select "ELITE FC" and "Medeo".
4.  Dashboard shows fencers from **both** clubs.
5.  Old tournaments still work (auto-migrated).
