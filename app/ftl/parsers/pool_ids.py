"""Pool ID extractor for FTL event pages."""
import re


def parse_pool_ids(html: str) -> dict:
    """
    Extract pool round ID and pool IDs from FTL event page HTML.

    Args:
        html: Raw HTML content from the FTL pools/scores page

    Returns:
        dict with keys:
            - pool_round_id: str - UUID of the pool round
            - pool_ids: list[str] - List of pool UUIDs (deduplicated, uppercase)

    Raises:
        ValueError: If parsing fails or required data is missing
    """
    # Extract the JavaScript array containing pool IDs
    pattern = r'var ids\s*=\s*\[(.*?)\];'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        raise ValueError("Could not find pool IDs array in HTML (missing 'var ids = [...]')")

    ids_string = match.group(1)

    # Extract individual UUIDs (32-character hex strings)
    pool_ids = re.findall(r'["\']([A-Fa-f0-9]{32})["\']', ids_string)
    if not pool_ids:
        raise ValueError("No pool IDs found in the JavaScript array")

    # Normalize to uppercase and deduplicate while preserving order
    seen = set()
    normalized_ids = []
    for pool_id in pool_ids:
        upper_id = pool_id.upper()
        if upper_id not in seen:
            seen.add(upper_id)
            normalized_ids.append(upper_id)

    # Extract pool round ID from URL context in the HTML
    round_id_pattern = r'pools/scores/[A-Fa-f0-9]{32}/([A-Fa-f0-9]{32})'
    round_match = re.search(round_id_pattern, html)
    if not round_match:
        raise ValueError("Could not find pool round ID in HTML")

    pool_round_id = round_match.group(1).upper()

    return {
        "pool_round_id": pool_round_id,
        "pool_ids": normalized_ids,
    }
