"""Tests for FTL pool HTML parser."""
import os
import re
import pytest
from app.ftl.parsers.pools import parse_pool_html


# Path to the actual FTL HTML sample artifact
SAMPLE_FILE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "comms", "ftl_research_human_pools.md"
)


def load_sample_html():
    """Load the actual FTL pool HTML sample from the research artifact."""
    with open(SAMPLE_FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract HTML from markdown code block
    html_match = re.search(r'```html\n(.*?)\n```', content, re.DOTALL)
    if not html_match:
        raise ValueError("Could not extract HTML from sample markdown file")

    return html_match.group(1)


class TestPoolHTMLParser:
    """Tests for parse_pool_html function using real FTL sample."""

    def test_parse_sample_pool_basic(self):
        """Test that parser can parse the sample HTML without errors."""
        html = load_sample_html()
        result = parse_pool_html(html, pool_id="130C4C6606F342AFBD607A193F05FAB1")

        assert result is not None
        assert isinstance(result, dict)
        assert 'pool_number' in result
        assert 'strip' in result
        assert 'fencers' in result
        assert 'bouts' in result

    def test_pool_number_extraction(self):
        """Test that pool number is correctly extracted."""
        html = load_sample_html()
        result = parse_pool_html(html)

        assert result['pool_number'] == 12

    def test_strip_assignment_extraction(self):
        """Test that strip assignment is correctly extracted."""
        html = load_sample_html()
        result = parse_pool_html(html)

        assert result['strip'] is not None
        assert result['strip'] == "A5"

    def test_fencers_list_extraction(self):
        """Test that all fencers are extracted from the pool."""
        html = load_sample_html()
        result = parse_pool_html(html)

        fencers = result['fencers']
        assert len(fencers) == 7  # Standard pool size

        # Check that fencer names are extracted
        fencer_names = [f['name'] for f in fencers]
        assert "IMREK Samuel A." in fencer_names
        assert "WANG justin" in fencer_names
        assert "MARTINEZ Carlos" in fencer_names

    def test_fencer_club_extraction(self):
        """Test that fencer clubs/affiliations are extracted."""
        html = load_sample_html()
        result = parse_pool_html(html)

        fencers = result['fencers']

        # Find WANG justin and check club
        wang = next((f for f in fencers if f['name'] == "WANG justin"), None)
        assert wang is not None
        assert wang['club'] is not None
        assert "CFC" in wang['club']
        assert "New England" in wang['club']

        # Find IMREK and check club
        imrek = next((f for f in fencers if f['name'] == "IMREK Samuel A."), None)
        assert imrek is not None
        assert imrek['club'] is not None
        assert "ALLIANCEFA" in imrek['club']

    def test_fencer_indicator_extraction(self):
        """Test that fencer indicators are extracted."""
        html = load_sample_html()
        result = parse_pool_html(html)

        fencers = result['fencers']

        # Check indicators for known fencers
        imrek = next((f for f in fencers if f['name'] == "IMREK Samuel A."), None)
        assert imrek is not None
        assert imrek['indicator'] == "+14"

        wang = next((f for f in fencers if f['name'] == "WANG justin"), None)
        assert wang is not None
        assert wang['indicator'] == "+5"

    def test_bouts_extraction(self):
        """Test that bouts are extracted from the score matrix."""
        html = load_sample_html()
        result = parse_pool_html(html)

        bouts = result['bouts']

        # With 7 fencers, there should be 21 bouts (7 choose 2)
        assert len(bouts) == 21

        # Check that each bout has required fields
        for bout in bouts:
            assert 'fencer_a' in bout
            assert 'fencer_b' in bout
            assert 'score_a' in bout
            assert 'score_b' in bout
            assert 'winner' in bout
            assert 'status' in bout

    def test_bout_winners_and_status(self):
        """Test that bout winners are correctly determined."""
        html = load_sample_html()
        result = parse_pool_html(html)

        bouts = result['bouts']

        # Count complete vs incomplete bouts
        complete_bouts = [b for b in bouts if b['status'] == 'complete']

        # All bouts in the sample should be complete
        assert len(complete_bouts) == 21

        # Check that complete bouts have winners
        for bout in complete_bouts:
            assert bout['winner'] in ['A', 'B']
            assert bout['score_a'] is not None
            assert bout['score_b'] is not None

    def test_specific_bout_scores(self):
        """Test that specific bout scores are parsed correctly from both matrix cells."""
        html = load_sample_html()
        result = parse_pool_html(html)

        bouts = result['bouts']

        # Find WANG vs PATEL bout
        # WANG (pos 2) cell shows D3 (WANG lost with 3 touches)
        # PATEL (pos 6) cell shows V3 (PATEL won, WANG scored 3)
        # Actual score should be PATEL 5, WANG 3
        wang_patel_bout = next(
            (b for b in bouts
             if (b['fencer_a'] == "WANG justin" and b['fencer_b'] == "PATEL Amir") or
                (b['fencer_a'] == "PATEL Amir" and b['fencer_b'] == "WANG justin")),
            None
        )

        assert wang_patel_bout is not None
        assert wang_patel_bout['status'] == 'complete'

        # PATEL won 5-3 over WANG
        if wang_patel_bout['fencer_a'] == "WANG justin":
            assert wang_patel_bout['score_a'] == 3
            assert wang_patel_bout['score_b'] == 5
            assert wang_patel_bout['winner'] == 'B'
        else:
            assert wang_patel_bout['score_a'] == 5
            assert wang_patel_bout['score_b'] == 3
            assert wang_patel_bout['winner'] == 'A'

    def test_priority_victory_scores(self):
        """Test bouts where winner scored 5-5 on priority."""
        html = load_sample_html()
        result = parse_pool_html(html)

        bouts = result['bouts']

        # IMREK vs WANG: both show V5/D5 (5-5 priority win for IMREK)
        # IMREK's cell: V5 (won, opponent scored 5)
        # WANG's cell: D5 (lost, WANG scored 5)
        # Score should be 5-5 with IMREK winning
        imrek_wang_bout = next(
            (b for b in bouts
             if (b['fencer_a'] == "IMREK Samuel A." and b['fencer_b'] == "WANG justin") or
                (b['fencer_a'] == "WANG justin" and b['fencer_b'] == "IMREK Samuel A.")),
            None
        )

        assert imrek_wang_bout is not None
        assert imrek_wang_bout['status'] == 'complete'

        # Should be 5-5 with IMREK as winner
        if imrek_wang_bout['fencer_a'] == "IMREK Samuel A.":
            assert imrek_wang_bout['score_a'] == 5
            assert imrek_wang_bout['score_b'] == 5
            assert imrek_wang_bout['winner'] == 'A'
        else:
            assert imrek_wang_bout['score_a'] == 5
            assert imrek_wang_bout['score_b'] == 5
            assert imrek_wang_bout['winner'] == 'B'

    def test_pool_id_passthrough(self):
        """Test that pool_id is included when provided."""
        html = load_sample_html()
        pool_id = "130C4C6606F342AFBD607A193F05FAB1"
        result = parse_pool_html(html, pool_id=pool_id)

        assert result['pool_id'] == pool_id

    def test_missing_pool_number_raises_error(self):
        """Test that missing pool number raises ValueError."""
        html = "<html><body><p>No pool data here</p></body></html>"

        with pytest.raises(ValueError, match="Could not find pool number"):
            parse_pool_html(html)

    def test_missing_fencer_rows_raises_error(self):
        """Test that missing fencer rows raises ValueError."""
        html = """
        <html>
            <body>
                <h4 class="poolNum">Pool #1</h4>
                <table class="poolTable">
                    <thead><tr><th>Header</th></tr></thead>
                    <tbody></tbody>
                </table>
            </body>
        </html>
        """

        with pytest.raises(ValueError, match="Could not find any fencer rows"):
            parse_pool_html(html)

    def test_strip_optional_when_missing(self):
        """Test that strip is None when not present in HTML."""
        html = """
        <html>
            <body>
                <h4 class="poolNum">Pool #5</h4>
                <table class="poolTable">
                    <tbody>
                        <tr class="poolRow">
                            <td>
                                <span class="poolCompName">TEST Fencer</span>
                                <br /><span class="poolAffil">CLUB / Region / USA</span>
                            </td>
                            <td class="poolPos">1</td>
                            <td class="poolScoreFill"></td>
                        </tr>
                    </tbody>
                </table>
            </body>
        </html>
        """

        result = parse_pool_html(html)
        assert result['strip'] is None

    def test_incomplete_bout_one_sided_data(self):
        """Test handling of bouts where only one cell has data."""
        html = """
        <html>
            <body>
                <h4 class="poolNum">Pool #1</h4>
                <table class="poolTable">
                    <tbody>
                        <tr class="poolRow">
                            <td>
                                <span class="poolCompName">FENCER A</span>
                            </td>
                            <td class="poolPos">1</td>
                            <td class="poolScoreFill"></td>
                            <td class="poolScore poolScoreV"><span>V4</span></td>
                        </tr>
                        <tr class="poolRow">
                            <td>
                                <span class="poolCompName">FENCER B</span>
                            </td>
                            <td class="poolPos">2</td>
                            <td class="poolScore"><span></span></td>
                            <td class="poolScoreFill"></td>
                        </tr>
                    </tbody>
                </table>
            </body>
        </html>
        """

        result = parse_pool_html(html)
        bouts = result['bouts']

        # Should have 1 bout
        assert len(bouts) == 1

        bout = bouts[0]
        # Only fencer A's cell has V4, so:
        # - A won, B scored 4
        # - Status should be complete since we have V from A's side
        assert bout['fencer_a'] == 'FENCER A'
        assert bout['fencer_b'] == 'FENCER B'
        assert bout['score_a'] == 5
        assert bout['score_b'] == 4
        assert bout['winner'] == 'A'
        assert bout['status'] == 'complete'

    def test_bout_with_no_data(self):
        """Test handling of bouts with no score data (not yet fenced)."""
        html = """
        <html>
            <body>
                <h4 class="poolNum">Pool #1</h4>
                <table class="poolTable">
                    <tbody>
                        <tr class="poolRow">
                            <td><span class="poolCompName">FENCER A</span></td>
                            <td class="poolPos">1</td>
                            <td class="poolScoreFill"></td>
                            <td class="poolScore"><span></span></td>
                        </tr>
                        <tr class="poolRow">
                            <td><span class="poolCompName">FENCER B</span></td>
                            <td class="poolPos">2</td>
                            <td class="poolScore"><span></span></td>
                            <td class="poolScoreFill"></td>
                        </tr>
                    </tbody>
                </table>
            </body>
        </html>
        """

        result = parse_pool_html(html)
        bouts = result['bouts']

        assert len(bouts) == 1
        bout = bouts[0]

        # No data for this bout
        assert bout['score_a'] is None
        assert bout['score_b'] is None
        assert bout['winner'] is None
        assert bout['status'] == 'incomplete'
