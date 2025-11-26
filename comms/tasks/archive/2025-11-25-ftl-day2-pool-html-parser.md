# Task: FTL Day 2 — Pool HTML Parser (strip/bout details)
**Owner:** ARCHITECT  
**Role:** Developer (implementer)  
**Status:** SPEC READY  
**Date:** 2025-11-25

## Objective
Parse the FencingTimeLive pool HTML to extract strip assignments, fencer names/clubs, scores, and bout states. Build on the existing FTL module in `app/ftl/`.

## Deliverables
1) Pool HTML parser that returns structured pool data (per pool ID).  
2) Tests using the captured sample HTML (`comms/ftl_research_human_pools.md`).  
3) Pydantic schema updates for pool data responses.  

## Scope & Constraints
- Synchronous parsing only (no concurrency changes yet).  
- No API routes/UI in this task; parser and tests only.  
- Keep existing code untouched outside `app/ftl/*` and tests.  
- No email/push.  

## Implementation Details

### 1) Data shape (per pool)
Create/extend Pydantic models in `app/ftl/schemas.py`:
- `PoolBout`: `fencer_a`, `fencer_b` (names), `score_a`, `score_b`, `winner` (`"A"|"B"|None`), `status` (`"complete"|"incomplete"`).
- `PoolFencer`: `name`, `club` (optional), `seed` (optional), `indicator` (e.g., `+`/`-` if present).
- `PoolDetails`: `pool_id`, `pool_number` (int), `strip` (str|None), `fencers: list[PoolFencer]`, `bouts: list[PoolBout]`.

### 2) Parser module
- Add `app/ftl/parsers/pools.py` with a function:
```python
def parse_pool_html(html: str, pool_id: str | None = None) -> dict:
    """
    Returns a PoolDetails-like dict.
    Raises ValueError on parse failures.
    """
```
- Use BeautifulSoup (already in requirements). No network calls inside parser.
- Inputs: raw HTML string for a single pool page; `pool_id` is optional (useful for returning the id if known).

### 3) Extraction rules (based on sample `comms/ftl_research_human_pools.md`)
- Strip: usually in a header like “Strip: A5” or similar; return `None` if absent.
- Pool number: present in header (“Pool #12”).
- Fencers table: names and clubs in rows; capture name, club (if present), seed/order if provided; ignore blank rows.
- Bouts table: matrix with scores; derive bouts by row/col labels.
  - Winner: higher score when both present; `None` if incomplete/missing.
  - Status: `"complete"` if both scores present; otherwise `"incomplete"`.
  - Ensure you don’t duplicate bouts (A vs B once).
- Normalize whitespace; keep original casing for names/clubs.

### 4) Tests
- Add `tests/ftl/test_pools_parser.py`:
  - Load the sample HTML from `comms/ftl_research_human_pools.md` (similar to Day 1 tests).
  - Assert strip is parsed (e.g., contains “A” or a known strip from sample), pool_number matches the sample, and at least one bout is marked complete with winner.
  - Spot-check a few known fencer names from the sample and their clubs if present.
  - Error cases: missing tables should raise `ValueError`.

### 5) Wiring
- No DB or API wiring yet.
- Ensure `__init__.py` exports new parser if helpful (optional).

## Acceptance Criteria
- `parse_pool_html` returns a dict matching `PoolDetails` for the sample file without exceptions.
- Extracted data includes pool number, strip (when present), fencers list, and bout results with winners where scores exist.
- Tests pass: `pytest tests/ftl/test_pools_parser.py`.
- No regressions to Day 1 tests.

## Out of Scope
- JSON pool results endpoint parsing (advancement).
- DE tableau parsing.
- Caching, concurrency, or API routes/UI.

## How to Run
```
pytest tests/ftl/test_pools_parser.py
```
