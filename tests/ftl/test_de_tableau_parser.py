"""Tests for DE tableau parser."""
import pytest
from app.ftl.parsers.de_tableau import parse_de_tableau


# Sample DE tableau HTML based on FTL API specification
SAMPLE_DE_TABLEAU_HTML = """
<html>
<body>
<table class='elimTableau w-100'>
    <tr>
        <th>Table of 64</th>
        <th>Table of 32</th>
        <th>Table of 16</th>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <!-- Match 1: Completed match with score -->
    <tr>
        <td class='tbb'>
            <span class='tseed'>(1)&nbsp;</span>
            <span class='tcln'>IMREK</span>
            <span class='tcfn'>Elijah</span>
            <span class='tcaff'>
                <br/>
                NOTREDAME / Gulf Coast / USA
            </span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <td class='tbr tscoref'>
            <span class='tsco'>
                15 - 8<br/>
                <span class='tref'>
                    Ref ALFORD April C. FIT / North Texas / USA
                </span>
                <br/>
                <span class='tref'>11:31 AM &#160;Strip L1</span>
                &nbsp;
            </span>
        </td>
        <td class='tbb'>
            <span class='tseed'>(1)&nbsp;</span>
            <span class='tcln'>IMREK</span>
            <span class='tcfn'>Elijah</span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <td class='tbbr'>
            <span class='tseed'>(129)&nbsp;</span>
            <span class='tcln'>WU</span>
            <span class='tcfn'>Alistair</span>
            &nbsp;
        </td>
        <td class='tbr tscoref'>
            <span class='tsco'>&nbsp;</span>
        </td>
        <td>&nbsp;</td>
    </tr>

    <!-- Match 2: Bye (one fencer missing) -->
    <tr>
        <td class='tbb'>
            <span class='tseed'>(2)&nbsp;</span>
            <span class='tcln'>GAO</span>
            <span class='tcfn'>Daniel</span>
            <span class='tcaff'>
                <br/>
                CFC
            </span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <td class='tbr tscoref'>
            <span class='tsco'>&nbsp;</span>
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <td class='tbbr'>
            <span class='tseed'>(256)&nbsp;</span>
            <span class='tcln'>- BYE -</span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <!-- Match 3: Pending match (both fencers present, no score) -->
    <tr>
        <td class='tbb'>
            <span class='tseed'>(45)&nbsp;</span>
            <span class='tcln'>WANG</span>
            <span class='tcfn'>Justin</span>
            <span class='tcaff'>
                <br/>
                CFC
            </span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <td class='tbr tscoref'>
            <span class='tsco'>&nbsp;</span>
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <td class='tbbr'>
            <span class='tseed'>(98)&nbsp;</span>
            <span class='tcln'>SMITH</span>
            <span class='tcfn'>John</span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <!-- Match 4: Completed match with priority (equal scores) -->
    <tr>
        <td class='tbb'>
            <span class='tseed'>(10)&nbsp;</span>
            <span class='tcln'>JONES</span>
            <span class='tcfn'>Sarah</span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <td class='tbr tscoref'>
            <span class='tsco'>
                10 - 10<br/>
                <span class='tref'>2:15 PM Strip A3</span>
                &nbsp;
            </span>
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

    <tr>
        <td class='tbbr'>
            <span class='tseed'>(55)&nbsp;</span>
            <span class='tcln'>DAVIS</span>
            <span class='tcfn'>Michael</span>
            &nbsp;
        </td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>

</table>
</body>
</html>
"""


# Minimal HTML with no tableau table (error case)
NO_TABLEAU_HTML = """
<html>
<body>
<div>No tableau here</div>
</body>
</html>
"""


# Empty tableau (just headers, no matches)
EMPTY_TABLEAU_HTML = """
<html>
<body>
<table class='elimTableau w-100'>
    <tr>
        <th>Table of 64</th>
        <th>Table of 32</th>
    </tr>
</table>
</body>
</html>
"""


class TestParseDeTableau:
    """Tests for parse_de_tableau function."""

    def test_basic_parsing(self):
        """Test basic tableau parsing returns expected structure."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)

        assert 'event_id' in result
        assert 'round_id' in result
        assert 'matches' in result
        assert isinstance(result['matches'], list)

    def test_event_and_round_ids(self):
        """Test event_id and round_id are properly included."""
        result = parse_de_tableau(
            SAMPLE_DE_TABLEAU_HTML,
            event_id='test-event-123',
            round_id='test-round-456'
        )

        assert result['event_id'] == 'test-event-123'
        assert result['round_id'] == 'test-round-456'

    def test_completed_match_extraction(self):
        """Test extraction of completed match with scores."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Find the IMREK vs WU match
        imrek_match = None
        for match in matches:
            if match.get('name_a') == 'IMREK Elijah' and match.get('name_b') == 'WU Alistair':
                imrek_match = match
                break

        assert imrek_match is not None, "Should find IMREK vs WU match"
        assert imrek_match['seed_a'] == 1
        assert imrek_match['seed_b'] == 129
        assert imrek_match['score_a'] == 15
        assert imrek_match['score_b'] == 8
        assert imrek_match['winner'] == 'A'
        assert imrek_match['status'] == 'complete'
        assert imrek_match['strip'] == 'L1'
        assert imrek_match['time'] == '11:31 AM'
        assert imrek_match['club_a'] == 'NOTREDAME / Gulf Coast / USA'

    def test_bye_handling(self):
        """Test handling of byes (one fencer missing)."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Find the GAO vs BYE match
        bye_match = None
        for match in matches:
            if match.get('name_a') == 'GAO Daniel' or match.get('name_b') == '- BYE -':
                bye_match = match
                break

        assert bye_match is not None, "Should find match with BYE"
        # At least one fencer should be present
        assert bye_match.get('name_a') or bye_match.get('name_b')

    def test_pending_match(self):
        """Test extraction of pending match (both fencers, no score)."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Find the WANG vs SMITH match
        pending_match = None
        for match in matches:
            if match.get('name_a') == 'WANG Justin' and match.get('name_b') == 'SMITH John':
                pending_match = match
                break

        assert pending_match is not None, "Should find WANG vs SMITH match"
        assert pending_match['seed_a'] == 45
        assert pending_match['seed_b'] == 98
        assert pending_match['score_a'] is None
        assert pending_match['score_b'] is None
        assert pending_match['winner'] is None
        assert pending_match['status'] in ['pending', 'in_progress']

    def test_priority_tie(self):
        """Test match with equal scores (priority win)."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Find the JONES vs DAVIS match
        tie_match = None
        for match in matches:
            if match.get('name_a') == 'JONES Sarah' and match.get('name_b') == 'DAVIS Michael':
                tie_match = match
                break

        assert tie_match is not None, "Should find JONES vs DAVIS match"
        assert tie_match['score_a'] == 10
        assert tie_match['score_b'] == 10
        assert tie_match['winner'] is None  # Equal scores, winner unknown without priority info
        assert tie_match['status'] == 'complete'
        assert tie_match['strip'] == 'A3'
        assert tie_match['time'] == '2:15 PM'

    def test_round_detection(self):
        """Test round labels are correctly extracted."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # All matches should have a round label
        for match in matches:
            assert match.get('round') in ['64', '32', '16', None]

    def test_seed_extraction(self):
        """Test seed numbers are correctly parsed."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Check various seeds were extracted
        seeds_found = set()
        for match in matches:
            if match.get('seed_a'):
                seeds_found.add(match['seed_a'])
            if match.get('seed_b'):
                seeds_found.add(match['seed_b'])

        assert 1 in seeds_found
        assert 129 in seeds_found
        assert 45 in seeds_found

    def test_club_extraction(self):
        """Test club/affiliation is correctly extracted."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Find match with club info
        clubs_found = []
        for match in matches:
            if match.get('club_a'):
                clubs_found.append(match['club_a'])
            if match.get('club_b'):
                clubs_found.append(match['club_b'])

        assert any('NOTREDAME' in club for club in clubs_found)
        assert any('CFC' in club for club in clubs_found)

    def test_strip_extraction(self):
        """Test strip assignment is correctly parsed."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        strips_found = set()
        for match in matches:
            if match.get('strip'):
                strips_found.add(match['strip'])

        assert 'L1' in strips_found
        assert 'A3' in strips_found

    def test_time_extraction(self):
        """Test match time is correctly parsed."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        times_found = set()
        for match in matches:
            if match.get('time'):
                times_found.add(match['time'])

        assert '11:31 AM' in times_found
        assert '2:15 PM' in times_found

    def test_winner_determination(self):
        """Test winner is correctly determined from scores."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Find completed match
        for match in matches:
            if match.get('score_a') == 15 and match.get('score_b') == 8:
                assert match['winner'] == 'A'
                break

    def test_missing_tableau_table_raises_error(self):
        """Test parsing raises ValueError when tableau table is missing."""
        with pytest.raises(ValueError, match="Could not find DE tableau table"):
            parse_de_tableau(NO_TABLEAU_HTML)

    def test_empty_tableau(self):
        """Test parsing empty tableau returns empty matches list."""
        result = parse_de_tableau(EMPTY_TABLEAU_HTML)

        assert result['matches'] == []

    def test_match_status_values(self):
        """Test all matches have valid status values."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        valid_statuses = {'complete', 'in_progress', 'pending'}
        for match in matches:
            assert match['status'] in valid_statuses

    def test_optional_fields_can_be_none(self):
        """Test optional fields can be None."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Should have at least one match
        assert len(matches) > 0

        # Check that optional fields exist
        for match in matches:
            assert 'id' in match
            assert 'note' in match
            assert 'path' in match
            # These can be None
            assert match['id'] is None  # Not extracted from sample HTML
            # note/path may or may not be None

    def test_name_concatenation(self):
        """Test first and last names are properly concatenated."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Find match with full name
        for match in matches:
            if match.get('name_a') == 'IMREK Elijah':
                # Name properly formatted
                assert 'IMREK' in match['name_a']
                assert 'Elijah' in match['name_a']
                break

    def test_match_count(self):
        """Test expected number of matches are extracted."""
        result = parse_de_tableau(SAMPLE_DE_TABLEAU_HTML)
        matches = result['matches']

        # Sample has 4 matches: IMREK vs WU, GAO vs BYE, WANG vs SMITH, JONES vs DAVIS
        assert len(matches) >= 4, f"Expected at least 4 matches, got {len(matches)}"
