# Task: Fix Live Dashboard Status (Active vs Waiting)

**Date:** 2026-01-31
**Owner:** ARCHITECT
**Status:** Ready for development

## Objective

Fix the live dashboard so active fencers appear under **Active Now** instead of **Waiting**. This should work for both pools and DE, with special focus on the current live event:
`https://www.fencingtimelive.com/tournaments/eventSchedule/734DE476CF78416BB38995DF9297E080`

## Background / Evidence

Live verification against the above event showed:
- Pool pages **do** include strip assignments (e.g., `On strip 5`) and the pool parser extracts them correctly.
- DE tableau HTML (from `/tableaus/scores/.../trees/.../tables/...`) includes `ttistr` spans like `7:54 PM Strip 5`.
- The DE parser currently produces **0 in_progress matches**; all non-complete matches are `pending`.
- Because DE status is ranked higher than pools in `_merge_status`, a DE `waiting` status overrides a pool `active` status, causing everyone to show as waiting.

Root suspicion: the DE parser never sets `status = "in_progress"` for matches without scores, and it fails to map `ttistr` strip info to the right match.

## Scope (In)

1. **DE parser status logic:** Ensure live DE matches with strip/time are marked `in_progress` and expose strip/time to the match.
2. **DE parser matching for `ttistr`:** Map floating strip info to the correct match (not only row `i+3`).
3. **Status merge rule:** Ensure `active` always wins over `waiting`, even across phases.

## Scope (Out)

- UI changes
- New endpoints
- Auto-refresh
- Deep redesign of parsers unrelated to status classification

## Files To Modify

- `app/ftl/parsers/de_tableau.py`
- `app/services/tournament_service.py`
- (Optional) add/extend tests in `tests/ftl/test_de_tableau_parser.py`

## Requirements

### 1) DE parser: live match detection

When both fencers are present and no score is present:
- If **strip is known** (from `ttistr` or score cell), set `status = "in_progress"`.
- If strip is not known, leave as `pending`.

### 2) DE parser: strip/time assignment from `ttistr`

Current logic only checks `i+3` row for `ttistr`, which is too fragile.
Implement more reliable mapping:

Suggested approach (pseudo):
```
when match_data is created:
  search a bounded window of rows after fencer A (e.g., i+1 .. i+8)
  for any `span.ttistr` in same or adjacent column(s)
  if found:
     parse time + strip
     assign to match_data
     set status = "in_progress" if scores are missing
```

Constraints:
- Keep scanning bounded to avoid large O(n^2) blowups.
- Prefer matches in the same column; fallback to adjacent column only if needed.
- Do not overwrite a valid score-derived strip/time.

### 3) Status merge priority

In `_merge_status`, add a **preference for "active" over "waiting"** regardless of phase.

Example rule:
- If `candidate.activity == "active"` and `existing.activity != "active"`, return `candidate`.
- If both are `active`, fall back to phase/activity ranking as currently implemented.

This prevents DE `waiting` from overriding pool `active`.

## Acceptance Criteria

- For the live event above, at least one DE match with `ttistr` is marked `in_progress` and appears under **Active Now**.
- A fencer who has a pool strip assigned shows as **Active**, even if a DE match exists but is `pending`.
- No regression: completed DE matches still show as `complete` with correct results.

## Suggested Tests

1. **DE parser unit test:** Add a minimal HTML fixture with a `ttistr` span near a pending match and assert `status == "in_progress"` and `strip` parsed.
2. **Merge behavior:** Add a small unit test for `_merge_status` to verify `active` beats `waiting` across phases.

## Notes

Live IDs used during validation:
- Event ID: `7C3CB2893CD34EB8B911D0AE3A67DEEF`
- Pool round ID: `1B2503ECB4D741508A97B6438F643C27`
- DE round ID: `5429C04FE2D24E08AC6D72E63BD1CB81`

Use these for optional manual smoke testing if needed.
