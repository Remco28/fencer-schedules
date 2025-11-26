"""Pool HTML parser for FTL individual pool pages."""
import re
from typing import Optional
from bs4 import BeautifulSoup


def parse_pool_html(html: str, pool_id: str | None = None) -> dict:
    """
    Parse FTL individual pool HTML to extract strip, fencers, and bout results.

    Args:
        html: Raw HTML content from a single pool page
        pool_id: Optional pool UUID for inclusion in response

    Returns:
        dict matching PoolDetails schema with keys:
            - pool_id: str | None
            - pool_number: int
            - strip: str | None
            - fencers: list[dict] (name, club, seed, indicator)
            - bouts: list[dict] (fencer_a, fencer_b, score_a, score_b, winner, status)

    Raises:
        ValueError: If parsing fails or required data is missing
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Extract pool number (required)
    pool_num_elem = soup.find('h4', class_='poolNum')
    if not pool_num_elem:
        raise ValueError("Could not find pool number element (h4.poolNum)")

    pool_num_match = re.search(r'Pool\s+#?(\d+)', pool_num_elem.text)
    if not pool_num_match:
        raise ValueError(f"Could not extract pool number from text: {pool_num_elem.text}")

    pool_number = int(pool_num_match.group(1))

    # Extract strip assignment (optional)
    strip = None
    strip_elem = soup.find('span', class_='poolStripTime')
    if strip_elem:
        strip_match = re.search(r'strip\s+([A-Z]\d+)', strip_elem.text, re.IGNORECASE)
        if strip_match:
            strip = strip_match.group(1).upper()

    # Extract fencers from pool table
    fencers = []
    fencer_rows = soup.find_all('tr', class_='poolRow')

    if not fencer_rows:
        raise ValueError("Could not find any fencer rows (tr.poolRow)")

    for row in fencer_rows:
        # Fencer name (required for each row)
        name_elem = row.find('span', class_='poolCompName')
        if not name_elem:
            continue  # Skip rows without a name (shouldn't happen but be defensive)

        name = name_elem.get_text(strip=True)

        # Club affiliation (optional)
        club = None
        affil_elem = row.find('span', class_='poolAffil')
        if affil_elem:
            club = affil_elem.get_text(strip=True)

        # Indicator (from final statistics column)
        indicator = None
        result_cells = row.find_all('td', class_='poolResult')
        if len(result_cells) >= 5:
            # 5th column is indicator (+14, -5, etc.)
            indicator = result_cells[4].get_text(strip=True)

        fencers.append({
            'name': name,
            'club': club,
            'seed': None,  # Not available in pool HTML
            'indicator': indicator
        })

    # Extract bouts from the score matrix
    # We need to parse both cells (A vs B and B vs A) to get accurate scores
    bouts = []

    # Build a score matrix lookup: [row_idx][col_idx] -> score_text
    score_matrix = {}
    for i, row in enumerate(fencer_rows):
        score_cells = row.find_all('td', class_='poolScore')
        score_matrix[i] = {}

        cell_idx = 0
        for j in range(len(fencers)):
            if i == j:
                # Diagonal - skip
                continue

            if cell_idx < len(score_cells):
                score_cell = score_cells[cell_idx]
                if 'poolScoreFill' not in score_cell.get('class', []):
                    score_span = score_cell.find('span')
                    if score_span:
                        score_matrix[i][j] = score_span.get_text(strip=True)
            cell_idx += 1

    # Now create bouts by combining both directions
    for i in range(len(fencers)):
        for j in range(i + 1, len(fencers)):  # Only process upper triangle to avoid duplicates
            fencer_a_name = fencers[i]['name']
            fencer_b_name = fencers[j]['name']

            # Get both cells: i→j and j→i
            cell_a_vs_b = score_matrix.get(i, {}).get(j, '')
            cell_b_vs_a = score_matrix.get(j, {}).get(i, '')

            # Parse both cells
            def parse_score_cell(text):
                """Parse V5 or D3 notation. Returns (touches, is_victory)."""
                if not text:
                    return None, None
                v_match = re.match(r'V(\d+)', text)
                d_match = re.match(r'D(\d+)', text)
                if v_match:
                    return int(v_match.group(1)), True
                elif d_match:
                    return int(d_match.group(1)), False
                return None, None

            touches_a, victory_a = parse_score_cell(cell_a_vs_b)
            touches_b, victory_b = parse_score_cell(cell_b_vs_a)

            # Determine actual scores and winner
            score_a = None
            score_b = None
            winner = None
            status = 'incomplete'

            if touches_a is not None and touches_b is not None:
                # Both cells have data - reconstruct the bout
                status = 'complete'

                if victory_a and not victory_b:
                    # A won, B lost
                    # A's cell shows their opponent's touches (what B scored)
                    # B's cell shows their own touches (what B scored)
                    score_a = 5  # Winner scored 5 (standard pool bout)
                    score_b = touches_b  # Loser's touches from their own cell
                    winner = 'A'
                elif not victory_a and victory_b:
                    # B won, A lost
                    score_a = touches_a  # Loser's touches from their own cell
                    score_b = 5  # Winner scored 5
                    winner = 'B'
                elif victory_a and victory_b:
                    # Both show victory? This shouldn't happen in valid data
                    # Treat as incomplete
                    score_a = None
                    score_b = None
                    winner = None
                    status = 'incomplete'
                else:
                    # Both show defeat? Also shouldn't happen
                    score_a = None
                    score_b = None
                    winner = None
                    status = 'incomplete'
            elif touches_a is not None:
                # Only A's cell has data
                if victory_a:
                    score_a = 5
                    score_b = touches_a  # Opponent's score from A's cell
                    winner = 'A'
                    status = 'complete'
                else:
                    score_a = touches_a  # A's score from their own cell
                    score_b = None  # Unknown
                    winner = 'B'  # B must have won if A shows defeat
                    status = 'incomplete'  # Can't determine B's exact score
            elif touches_b is not None:
                # Only B's cell has data
                if victory_b:
                    score_a = touches_b  # Opponent's score from B's cell
                    score_b = 5
                    winner = 'B'
                    status = 'complete'
                else:
                    score_a = None  # Unknown
                    score_b = touches_b  # B's score from their own cell
                    winner = 'A'  # A must have won if B shows defeat
                    status = 'incomplete'  # Can't determine A's exact score
            # else: both are None, leave as incomplete

            bouts.append({
                'fencer_a': fencer_a_name,
                'fencer_b': fencer_b_name,
                'score_a': score_a,
                'score_b': score_b,
                'winner': winner,
                'status': status
            })

    return {
        'pool_id': pool_id,
        'pool_number': pool_number,
        'strip': strip,
        'fencers': fencers,
        'bouts': bouts
    }
