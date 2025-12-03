# Task: FTL Day 5 — DE Tableau Parser (Elimination Bracket)
**Date:** 2025-11-26  
**Owner:** ARCHITECT  
**Status:** Ready for development  

## Objective
Parse the FencingTimeLive DE tableau HTML (`/tableaus/scores/{eventID}/{roundID}`) to extract bracket positions, match scores, strip assignments, and fencer elimination/advancement status. Provide structured data to drive “Where is my fencer in DE?” and “Are they eliminated?” views.

## Inputs
- HTML from `GET /tableaus/scores/{eventID}/{roundID}`.
- Fixture: `comms/ftl_research_human.md` (DE tableau sample). If needed, augment with a second sample showing ongoing matches and byes.

## Deliverables
1. New parser module `app/ftl/parsers/de_tableau.py` with public `parse_de_tableau(html: str, *, event_id: str | None = None, round_id: str | None = None) -> dict`.
2. Pydantic schemas added to `app/ftl/schemas.py`:
   - `TableauMatch`: `id: str | None`, `round: str | None` (e.g., "64", "32", "16", "8", "SF", "F"), `seed_a: int | None`, `seed_b: int | None`, `name_a: str | None`, `name_b: str | None`, `club_a: str | None`, `club_b: str | None`, `score_a: int | None`, `score_b: int | None`, `winner: str | None` ("A"/"B"), `status: str` ("complete", "in_progress", "pending"), `strip: str | None`, `time: str | None`, `note: str | None` (e.g., referee info), `path: str | None` (optional bracket position identifier).
   - `Tableau`: `event_id: str | None`, `round_id: str | None`, `matches: list[TableauMatch]`.
3. Unit tests in `tests/ftl/test_de_tableau_parser.py` covering full parse, in-progress/empty matches, byes, and winner detection.
4. Documentation updates (log, next steps) noting spec and implementation status.

## Parsing Contract
- Extract each match node (completed or pending). Key selectors from sample HTML:
  - Last name: `.tcln`
  - First name: `.tcfn`
  - Seed: `.tseed` (e.g., `(45)`)
  - Club/division: `.tcaff` (strip `<br/>` fragments; keep plain text without flag span)
  - Score block: `.tsco`; empty/non-breaking space means match not started.
  - Strip/time/ref: inside `.tsco` (e.g., `11:31 AM  Strip L1`).
- Round detection:
  - Use DOM structure or surrounding labels; if unavailable, infer from bracket column index (map columns to "64", "32", "16", "8", "SF", "F"). Document chosen approach in code comments.
- Status:
  - `complete` if both scores present or score block contains a numeric score.
  - `in_progress` if `.tsco` contains a non-breaking space but names are present.
  - `pending` if names/seeds exist but `.tsco` empty/whitespace.
- Winner:
  - Compare `score_a` vs `score_b`; if equal but present, leave `winner=None` (priority unknown).
  - If `.tsco` includes explicit winner styling (not seen in sample), respect it; otherwise infer by higher score.
- Names:
  - Concatenate first/last with a space, preserve casing as provided.
  - Handle missing first names (use last only).
- Seeds:
  - Parse integers from `(45)` format; if missing, set `None`.
- Clubs:
  - Extract plain text from `.tcaff`, remove flag spans and excess whitespace; keep single string per fencer.
- Strip/time:
  - Parse from `.tsco` trailing line (e.g., `Strip L1`); set `None` if absent.
- Handle byes/empty slots:
  - If one side missing entirely, set corresponding name/seed/club to `None`; status should still be `pending` or `complete` if bye auto-advances (set winner to the present side if a winner can be inferred).

## Testing Requirements
- Use the fixture HTML to assert:
  - Correct match count per sample (document expected number in test).
  - Round labeling present on all matches.
  - Winner/score extraction for completed matches.
  - `pending` status for empty `.tsco`; `in_progress` when `.tsco` exists but has no score and both fencers present.
  - Strip assignment parsed where present; None when absent.
  - Seeds parsed as ints; names/clubs stripped of whitespace.
- Edge cases:
  - Missing `.tsco` → pending.
  - One-sided match (bye) → winner inferred if appropriate.
  - Priority ties not represented; if equal scores, winner remains None.
- No network calls; tests should load fixture from `comms/ftl_research_human.md`.

## Out of Scope
- HTTP fetching (handled by client).
- Database persistence or caching.
- API endpoints.
- Pool/DE integration logic.

## Acceptance Criteria
- New parser returns data compatible with `Tableau` schema.
- Tests in `tests/ftl/test_de_tableau_parser.py` pass via `.venv/bin/pytest tests/ftl`.
- Existing tests remain green.
- Docs updated (log, manifest, next steps).
