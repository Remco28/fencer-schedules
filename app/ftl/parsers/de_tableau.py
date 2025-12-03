"""DE Tableau parser for FTL elimination bracket pages."""
import re
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
        cells = row.find_all('td')

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

                # Look ahead for score row (next row, same column)
                if i + 1 < len(rows):
                    score_row = rows[i + 1]
                    score_cells = score_row.find_all('td')
                    if col_idx < len(score_cells):
                        score_cell = score_cells[col_idx]
                        if score_cell.find('span', class_='tsco') or 'tscoref' in score_cell.get('class', []):
                            score_data = _extract_score_from_cell(score_cell)
                            match_data['score_a'] = score_data['score_a']
                            match_data['score_b'] = score_data['score_b']
                            match_data['winner'] = score_data['winner']
                            match_data['status'] = score_data['status']
                            match_data['strip'] = score_data['strip']
                            match_data['time'] = score_data['time']
                            match_data['note'] = score_data['note']

                # Look ahead for fencer B row (two rows ahead, same column)
                if i + 2 < len(rows):
                    fencer_b_row = rows[i + 2]
                    fencer_b_cells = fencer_b_row.find_all('td')
                    if col_idx < len(fencer_b_cells):
                        fencer_b_cell = fencer_b_cells[col_idx]
                        if 'tbbr' in fencer_b_cell.get('class', []):
                            fencer_b_data = _extract_fencer_from_cell(fencer_b_cell)
                            match_data['seed_b'] = fencer_b_data['seed']
                            match_data['name_b'] = fencer_b_data['name']
                            match_data['club_b'] = fencer_b_data['club']

                            # Update status based on both fencers present
                            if match_data['status'] == 'pending' and match_data['name_b'] and match_data['name_a']:
                                if match_data['score_a'] is None and match_data['score_b'] is None:
                                    match_data['status'] = 'in_progress'

                # Save match
                matches.append(match_data)

        i += 1

    return {
        'event_id': event_id,
        'round_id': round_id,
        'matches': matches,
    }


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
    if not score_span:
        return {
            'score_a': None,
            'score_b': None,
            'winner': None,
            'status': 'pending',
            'strip': None,
            'time': None,
            'note': None,
        }

    score_text = score_span.get_text(separator='\n', strip=True)

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
    ref_span = score_span.find('span', class_='tref')
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
