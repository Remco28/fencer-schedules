"""DE Tableau parser for FTL elimination bracket pages."""
import re
from bisect import bisect_right
from collections import defaultdict
from typing import Optional
from bs4 import BeautifulSoup, Tag


def parse_de_tableau(
    html: str,
    *,
    event_id: str | None = None,
    round_id: str | None = None
) -> dict:
    """
    Parse FTL DE tableau HTML to extract bracket matches, scores, and status.

    The HTML structure for a match is typically:
    - Row 1: Fencer A (cell with 'tbb' class)
    - Row 2: Score cell (cell with 'tsco' span)
    - Row 3: Fencer B (cell with 'tbbr' class)

    Args:
        html: Raw HTML content from DE tableau page
        event_id: Optional event UUID for inclusion in response
        round_id: Optional round UUID for inclusion in response

    Returns:
        dict matching Tableau schema with keys:
            - event_id: str | None
            - round_id: str | None
            - matches: list[dict] (each matching TableauMatch schema)

    Raises:
        ValueError: If parsing fails or required data is missing
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Find the main tableau table
    tableau_table = soup.find('table', class_='elimTableau')
    if not tableau_table:
        raise ValueError("Could not find DE tableau table (table.elimTableau)")

    # Get all rows from the table
    rows = tableau_table.find_all('tr')
    if not rows:
        raise ValueError("No rows found in tableau table")
    rows_cells = [row.find_all('td') for row in rows]

    # Pre-index top/bottom rows per column to avoid scanning large gaps.
    col_tbb_rows: dict[int, list[int]] = defaultdict(list)
    col_tbbr_rows: dict[int, list[int]] = defaultdict(list)
    for r_idx, cells in enumerate(rows_cells):
        for c_idx, cell in enumerate(cells):
            cell_classes = cell.get('class', [])
            has_name = cell.find('span', class_='tseed') or cell.find('span', class_='tcln')
            if not has_name:
                continue
            if 'tbb' in cell_classes:
                col_tbb_rows[c_idx].append(r_idx)
            elif 'tbbr' in cell_classes:
                col_tbbr_rows[c_idx].append(r_idx)

    # Detect round labels from header row
    round_labels = []
    header_row = rows[0] if rows and rows[0].find('th') else None
    if header_row:
        headers = header_row.find_all('th')
        for header in headers:
            text = header.get_text(strip=True)
            # Extract round from "Table of X" format
            match = re.search(r'Table of (\d+)', text)
            if match:
                round_labels.append(match.group(1))
            elif 'Semi' in text or 'SF' in text:
                round_labels.append('SF')
            elif 'Final' in text or 'Gold' in text:
                round_labels.append('F')

    matches = []
    i = 0

    # Skip header row(s)
    while i < len(rows) and rows[i].find('th'):
        i += 1

    # Parse matches by scanning for the pattern: fencer_a row, score row, fencer_b row
    while i < len(rows):
        row = rows[i]
        cells = rows_cells[i]

        if not cells:
            i += 1
            continue

        # Look for cells that might contain fencer A
        for col_idx, cell in enumerate(cells):
            cell_classes = cell.get('class', [])

            # Found fencer A cell (tbb class)
            if 'tbb' in cell_classes and (cell.find('span', class_='tseed') or cell.find('span', class_='tcln')):
                round_label = round_labels[col_idx] if col_idx < len(round_labels) else None
                fencer_a_data = _extract_fencer_from_cell(cell)

                # Initialize match
                match_data = {
                    'id': None,
                    'round': round_label,
                    'seed_a': fencer_a_data['seed'],
                    'name_a': fencer_a_data['name'],
                    'club_a': fencer_a_data['club'],
                    'seed_b': None,
                    'name_b': None,
                    'club_b': None,
                    'score_a': None,
                    'score_b': None,
                    'winner': None,
                    'status': 'pending',
                    'strip': None,
                    'time': None,
                    'note': None,
                    'path': None,
                }

                # Find Fencer B by using pre-indexed rows per column.
                b_row_index = None
                tbb_rows = col_tbb_rows.get(col_idx, [])
                tbbr_rows = col_tbbr_rows.get(col_idx, [])
                next_top = None
                next_bottom = None
                if tbb_rows:
                    pos = bisect_right(tbb_rows, i)
                    if pos < len(tbb_rows):
                        next_top = tbb_rows[pos]
                if tbbr_rows:
                    pos = bisect_right(tbbr_rows, i)
                    if pos < len(tbbr_rows):
                        next_bottom = tbbr_rows[pos]
                if next_bottom is not None and (next_top is None or next_bottom < next_top):
                    b_row_index = next_bottom

                if b_row_index is not None:
                    fencer_b_cells = rows_cells[b_row_index]
                    if col_idx < len(fencer_b_cells):
                        fencer_b_cell = fencer_b_cells[col_idx]
                        fencer_b_data = _extract_fencer_from_cell(fencer_b_cell)
                        match_data['seed_b'] = fencer_b_data['seed']
                        match_data['name_b'] = fencer_b_data['name']
                        match_data['club_b'] = fencer_b_data['club']

                    # Look for scores in a wider window, across adjacent columns
                    # to handle both legacy and newer layouts.
                    if match_data['score_a'] is None:
                        score_found = False
                        for s_idx in range(i, b_row_index + 1):
                            s_cells = rows_cells[s_idx]
                            for col_offset in (0, 1):
                                s_col = col_idx + col_offset
                                if s_col >= len(s_cells):
                                    continue
                                s_cell = s_cells[s_col]
                                if s_cell.find('span', class_='tsco') or 'tscoref' in s_cell.get('class', []) or re.search(r'\d+\s*-\s*\d+', s_cell.get_text(strip=True)):
                                    score_data = _extract_score_from_cell(s_cell)
                                    if score_data['score_a'] is not None or score_data['strip']:
                                        match_data['score_a'] = score_data['score_a']
                                        match_data['score_b'] = score_data['score_b']
                                        match_data['winner'] = score_data['winner']
                                        match_data['status'] = score_data['status']
                                        match_data['strip'] = score_data['strip']
                                        match_data['time'] = score_data['time']
                                        match_data['note'] = score_data['note']
                                        score_found = True
                                        break
                            if score_found:
                                break

                # Update status based on both fencers present and no scores
                if match_data['status'] == 'pending' and match_data['name_b'] and match_data['name_a']:
                    if match_data['score_a'] is None and match_data['score_b'] is None:
                        # Both fencers present but no score yet - active if strip already assigned
                        if match_data['strip']:
                            match_data['status'] = 'in_progress'

                # Look ahead for "Floating" Strip Info in a bounded window
                # In new FTL format, strip info (ttistr span) may appear in rows below the match
                # Search rows i+1 through i+8 for a ttistr span in same or adjacent column
                if (
                    match_data['status'] in ('pending',)
                    and match_data['strip'] is None
                    and not _is_bye_name(match_data['name_a'])
                    and not _is_bye_name(match_data['name_b'])
                ):
                    for strip_offset in range(1, 9):
                        if i + strip_offset >= len(rows):
                            break
                        strip_row = rows[i + strip_offset]
                        strip_cells = strip_row.find_all('td')

                        # Search cells in same column and adjacent columns
                        search_cols = [col_idx]
                        if col_idx > 0:
                            search_cols.append(col_idx - 1)
                        if col_idx + 1 < len(strip_cells):
                            search_cols.append(col_idx + 1)

                        found_strip = False
                        for search_col in search_cols:
                            if search_col >= len(strip_cells):
                                continue
                            s_cell = strip_cells[search_col]
                            ttistr = s_cell.find('span', class_='ttistr')
                            if ttistr:
                                # Parse "7:32 PM Strip 4"
                                text = ttistr.get_text(strip=True)
                                strip_match_result = re.search(r'Strip\s+([A-Z0-9]+)', text, re.IGNORECASE)
                                if strip_match_result:
                                    match_data['strip'] = strip_match_result.group(1).upper()
                                    # If it has a strip assignment, the match is active
                                    match_data['status'] = 'in_progress'

                                time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)', text, re.IGNORECASE)
                                if time_match and not match_data['time']:
                                    match_data['time'] = time_match.group(1)

                                found_strip = True
                                break

                        if found_strip:
                            break

                # Save match
                matches.append(match_data)

        i += 1

    return {
        'event_id': event_id,
        'round_id': round_id,
        'matches': matches,
    }


def _is_bye_name(name: Optional[str]) -> bool:
    """Return True if the name represents a BYE/placeholder entry."""
    if not name:
        return True
    return name.strip().upper() in {"- BYE -", "BYE"}


def _extract_fencer_from_cell(cell: Tag) -> dict:
    """Extract fencer data (seed, name, club) from a tableau cell."""
    seed = None
    seed_span = cell.find('span', class_='tseed')
    if seed_span:
        seed_text = seed_span.get_text(strip=True)
        seed_match = re.search(r'\((\d+)\)', seed_text)
        if seed_match:
            seed = int(seed_match.group(1))

    # Extract name (last + first)
    last_name = None
    first_name = None

    last_span = cell.find('span', class_='tcln')
    if last_span:
        last_name = last_span.get_text(strip=True)

    first_span = cell.find('span', class_='tcfn')
    if first_span:
        first_name = first_span.get_text(strip=True)

    # Combine name
    name_parts = []
    if last_name:
        name_parts.append(last_name)
    if first_name:
        name_parts.append(first_name)
    name = ' '.join(name_parts) if name_parts else None

    # Extract club/affiliation
    club = None
    club_span = cell.find('span', class_='tcaff')
    if club_span:
        # Remove flag spans and get plain text
        for flag in club_span.find_all('span'):
            flag.decompose()
        club_text = club_span.get_text(separator=' ', strip=True)
        # Clean up whitespace
        club = ' '.join(club_text.split()) if club_text else None

    return {
        'seed': seed,
        'name': name,
        'club': club,
    }


def _extract_score_from_cell(cell: Tag) -> dict:
    """Extract score data (scores, winner, strip, time) from a score cell."""
    score_span = cell.find('span', class_='tsco')
    score_text = None
    score_source = None
    if score_span:
        score_text = score_span.get_text(separator='\n', strip=True)
        score_source = score_span
    else:
        candidate = cell.get_text(separator='\n', strip=True)
        if 'tscoref' in cell.get('class', []) or cell.find(class_='tscoref') or re.search(r'\d+\s*-\s*\d+', candidate):
            score_text = candidate
            score_source = cell
        else:
            return {
                'score_a': None,
                'score_b': None,
                'winner': None,
                'status': 'pending',
                'strip': None,
                'time': None,
                'note': None,
            }

    # Extract scores (e.g., "15 - 8")
    score_a = None
    score_b = None
    winner = None
    status = 'pending'

    score_match = re.search(r'(\d+)\s*-\s*(\d+)', score_text)
    if score_match:
        score_a = int(score_match.group(1))
        score_b = int(score_match.group(2))
        status = 'complete'

        # Determine winner
        if score_a > score_b:
            winner = 'A'
        elif score_b > score_a:
            winner = 'B'
        # If equal, leave winner as None (priority situation)

    # Extract strip assignment (e.g., "Strip L1")
    strip = None
    strip_match = re.search(r'Strip\s+([A-Z]?\d+)', score_text, re.IGNORECASE)
    if strip_match:
        strip = strip_match.group(1)

    # Extract time (e.g., "11:31 AM")
    time = None
    time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)', score_text, re.IGNORECASE)
    if time_match:
        time = time_match.group(1).strip()

    # Extract referee note
    note = None
    ref_span = score_source.find('span', class_='tref') if score_source else None
    if ref_span:
        ref_text = ref_span.get_text(strip=True)
        # Remove strip and time from note
        ref_text = re.sub(r'\d{1,2}:\d{2}\s*(?:AM|PM)?', '', ref_text, flags=re.IGNORECASE)
        ref_text = re.sub(r'Strip\s+[A-Z]?\d+', '', ref_text, flags=re.IGNORECASE)
        note = ref_text.strip() if ref_text.strip() else None

    return {
        'score_a': score_a,
        'score_b': score_b,
        'winner': winner,
        'status': status,
        'strip': strip,
        'time': time,
        'note': note,
    }
