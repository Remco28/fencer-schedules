"""Tests for FTL pool results JSON parser."""
import os
import re
import json
import pytest
from app.ftl.parsers.pool_results import parse_pool_results


# Path to the pool results JSON sample fixture
SAMPLE_FILE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "comms", "ftl_research_human_pools_results.md"
)


def load_sample_json():
    """Load the pool results JSON sample from the research artifact."""
    with open(SAMPLE_FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract JSON from markdown code block
    json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
    if not json_match:
        raise ValueError("Could not extract JSON from sample markdown file")

    return json_match.group(1)


class TestPoolResultsParser:
    """Tests for parse_pool_results function using real FTL sample."""

    def test_parse_sample_json_string(self):
        """Test that parser can parse the sample JSON string without errors."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        assert result is not None
        assert isinstance(result, dict)
        assert 'event_id' in result
        assert 'pool_round_id' in result
        assert 'fencers' in result

    def test_parse_sample_json_list(self):
        """Test that parser accepts pre-parsed list of dicts."""
        json_str = load_sample_json()
        data = json.loads(json_str)
        result = parse_pool_results(data)

        assert result is not None
        assert isinstance(result, dict)
        assert 'fencers' in result

    def test_fencer_count(self):
        """Test that all fencers from fixture are parsed."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        fencers = result['fencers']
        # Our fixture has 6 fencers
        assert len(fencers) == 6

    def test_order_preservation(self):
        """Test that fencers are returned in input order (placement ascending)."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        fencers = result['fencers']
        places = [f['place'] for f in fencers if f['place'] is not None]

        # Places should be in ascending order (1, 2, 3, 125, 180, 250)
        assert places == sorted(places)

    def test_required_fields_present(self):
        """Test that all required fields are present for each fencer."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        for fencer in result['fencers']:
            assert 'fencer_id' in fencer
            assert 'name' in fencer
            assert 'victories' in fencer
            assert 'matches' in fencer
            assert 'status' in fencer

    def test_status_advanced_mapping(self):
        """Test that 'Advanced' prediction maps to 'advanced' status."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        # IMREK Elijah S. has prediction "Advanced"
        imrek = next((f for f in result['fencers'] if f['name'] == "IMREK Elijah S."), None)
        assert imrek is not None
        assert imrek['prediction_raw'] == "Advanced"
        assert imrek['status'] == "advanced"

        # GAO Daniel also has "Advanced"
        gao = next((f for f in result['fencers'] if f['name'] == "GAO Daniel"), None)
        assert gao is not None
        assert gao['status'] == "advanced"

    def test_status_eliminated_mapping(self):
        """Test that non-'Advanced' predictions map to 'eliminated' status."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        # SMITH John has prediction "Eliminated"
        smith = next((f for f in result['fencers'] if f['name'] == "SMITH John"), None)
        assert smith is not None
        assert smith['prediction_raw'] == "Eliminated"
        assert smith['status'] == "eliminated"

        # JONES Michael has prediction "Cut" (also eliminated)
        jones = next((f for f in result['fencers'] if f['name'] == "JONES Michael"), None)
        assert jones is not None
        assert jones['prediction_raw'] == "Cut"
        assert jones['status'] == "eliminated"

    def test_status_unknown_mapping(self):
        """Test that missing/empty prediction maps to 'unknown' status."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        # DOE Jane has empty prediction
        doe = next((f for f in result['fencers'] if f['name'] == "DOE Jane"), None)
        assert doe is not None
        assert doe['prediction_raw'] is None
        assert doe['status'] == "unknown"

    def test_numeric_field_parsing(self):
        """Test that numeric fields are parsed correctly."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        imrek = next((f for f in result['fencers'] if f['name'] == "IMREK Elijah S."), None)
        assert imrek is not None

        # Check numeric fields
        assert imrek['victories'] == 6
        assert imrek['matches'] == 6
        assert imrek['victory_ratio'] == 1.0
        assert imrek['touches_scored'] == 30
        assert imrek['touches_received'] == 9
        assert imrek['indicator'] == 21
        assert imrek['place'] == 1

    def test_optional_fields_as_none(self):
        """Test that missing optional fields become None."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        # DOE Jane has null division
        doe = next((f for f in result['fencers'] if f['name'] == "DOE Jane"), None)
        assert doe is not None
        assert doe['division'] is None

        # SMITH John has null club2
        smith = next((f for f in result['fencers'] if f['name'] == "SMITH John"), None)
        assert smith is not None
        assert smith['club_secondary'] is None

    def test_tie_flag_preserved(self):
        """Test that tie flag is preserved correctly."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        # JONES Michael has tie=true
        jones = next((f for f in result['fencers'] if f['name'] == "JONES Michael"), None)
        assert jones is not None
        assert jones['tie'] is True

        # IMREK has tie=false
        imrek = next((f for f in result['fencers'] if f['name'] == "IMREK Elijah S."), None)
        assert imrek is not None
        assert imrek['tie'] is False

    def test_club_fields_mapping(self):
        """Test that club1 and club2 map to club_primary and club_secondary."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        # IMREK has both clubs
        imrek = next((f for f in result['fencers'] if f['name'] == "IMREK Elijah S."), None)
        assert imrek is not None
        assert imrek['club_primary'] == "University Of Notre Dame NCAA"
        assert imrek['club_secondary'] == "Alliance Fencing Academy"

        # DOE has both clubs
        doe = next((f for f in result['fencers'] if f['name'] == "DOE Jane"), None)
        assert doe is not None
        assert doe['club_primary'] == "Northern Club"
        assert doe['club_secondary'] == "Second Club"

    def test_event_and_round_id_passthrough(self):
        """Test that event_id and pool_round_id are included when provided."""
        json_str = load_sample_json()
        event_id = "54B9EF9A9707492E93F1D1F46CF715A2"
        pool_round_id = "D6890CA440324D9E8D594D5682CC33B7"

        result = parse_pool_results(
            json_str,
            event_id=event_id,
            pool_round_id=pool_round_id
        )

        assert result['event_id'] == event_id
        assert result['pool_round_id'] == pool_round_id

    def test_event_and_round_id_none_by_default(self):
        """Test that event_id and pool_round_id default to None."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        assert result['event_id'] is None
        assert result['pool_round_id'] is None

    def test_invalid_json_string_raises_error(self):
        """Test that invalid JSON string raises ValueError."""
        invalid_json = "{ this is not valid json }"

        with pytest.raises(ValueError, match="Invalid JSON string"):
            parse_pool_results(invalid_json)

    def test_non_list_payload_raises_error(self):
        """Test that non-list top-level payload raises ValueError."""
        # JSON object instead of array
        json_str = '{"id": "123", "name": "Test"}'

        with pytest.raises(ValueError, match="Expected list payload"):
            parse_pool_results(json_str)

    def test_empty_list_raises_error(self):
        """Test that empty fencer list raises ValueError."""
        json_str = "[]"

        with pytest.raises(ValueError, match="Empty fencer list"):
            parse_pool_results(json_str)

    def test_missing_required_field_id_raises_error(self):
        """Test that missing 'id' field raises ValueError."""
        json_str = '[{"name": "Test", "v": 5, "m": 6}]'

        with pytest.raises(ValueError, match="Missing required field.*id"):
            parse_pool_results(json_str)

    def test_missing_required_field_name_raises_error(self):
        """Test that missing 'name' field raises ValueError."""
        json_str = '[{"id": "123", "v": 5, "m": 6}]'

        with pytest.raises(ValueError, match="Missing required field.*name"):
            parse_pool_results(json_str)

    def test_missing_required_field_v_raises_error(self):
        """Test that missing 'v' field raises ValueError."""
        json_str = '[{"id": "123", "name": "Test", "m": 6}]'

        with pytest.raises(ValueError, match="Missing required field.*v"):
            parse_pool_results(json_str)

    def test_missing_required_field_m_raises_error(self):
        """Test that missing 'm' field raises ValueError."""
        json_str = '[{"id": "123", "name": "Test", "v": 5}]'

        with pytest.raises(ValueError, match="Missing required field.*m"):
            parse_pool_results(json_str)

    def test_string_normalization(self):
        """Test that string fields are stripped of whitespace."""
        json_str = '''[{
            "id": "  123  ",
            "name": "  Test Name  ",
            "club1": "  Test Club  ",
            "div": "  Division  ",
            "country": "  USA  ",
            "v": 5,
            "m": 6
        }]'''

        result = parse_pool_results(json_str)
        fencer = result['fencers'][0]

        assert fencer['fencer_id'] == "123"
        assert fencer['name'] == "Test Name"
        assert fencer['club_primary'] == "Test Club"
        assert fencer['division'] == "Division"
        assert fencer['country'] == "USA"

    def test_case_insensitive_advanced_status(self):
        """Test that 'Advanced' prediction is case-insensitive (but we preserve raw)."""
        # Test with different cases
        test_cases = [
            ('{"prediction": "Advanced"}', "advanced"),
            ('{"prediction": "advanced"}', "advanced"),
            ('{"prediction": "ADVANCED"}', "advanced"),
        ]

        for prediction_json, expected_status in test_cases:
            full_json = f'[{{"id": "123", "name": "Test", "v": 5, "m": 6, "prediction": "{prediction_json.split(":")[1].strip()[1:-2]}"}}]'
            result = parse_pool_results(full_json)
            assert result['fencers'][0]['status'] == expected_status

    def test_indicator_as_int(self):
        """Test that indicator is converted to int."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        imrek = next((f for f in result['fencers'] if f['name'] == "IMREK Elijah S."), None)
        assert imrek is not None
        assert isinstance(imrek['indicator'], int)
        assert imrek['indicator'] == 21

    def test_victory_ratio_as_float(self):
        """Test that victory_ratio is a float."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        # GAO has vm=1 (int in JSON, should work)
        gao = next((f for f in result['fencers'] if f['name'] == "GAO Daniel"), None)
        assert gao is not None
        assert gao['victory_ratio'] == 1.0

        # SMITH has vm=0.667
        smith = next((f for f in result['fencers'] if f['name'] == "SMITH John"), None)
        assert smith is not None
        assert smith['victory_ratio'] == 0.667

    def test_invalid_input_type_raises_error(self):
        """Test that invalid input type (not str or list) raises ValueError."""
        with pytest.raises(ValueError, match="Expected str or list"):
            parse_pool_results(123)

        with pytest.raises(ValueError, match="Expected str or list"):
            parse_pool_results(None)

        with pytest.raises(ValueError, match="Expected str or list"):
            parse_pool_results({"foo": "bar"})

    def test_non_dict_fencer_raises_error(self):
        """Test that non-dict items in fencer list raise ValueError."""
        json_str = '[{"id": "123", "name": "Test", "v": 5, "m": 6}, "not a dict"]'

        with pytest.raises(ValueError, match="Fencer at index 1 is not a dict"):
            parse_pool_results(json_str)

    def test_complete_field_mapping(self):
        """Test complete field mapping from JSON to output schema."""
        json_str = load_sample_json()
        result = parse_pool_results(json_str)

        imrek = next((f for f in result['fencers'] if f['name'] == "IMREK Elijah S."), None)
        assert imrek is not None

        # Verify all fields are mapped
        expected_keys = {
            'fencer_id', 'name', 'club_primary', 'club_secondary', 'division',
            'country', 'place', 'victories', 'matches', 'victory_ratio',
            'touches_scored', 'touches_received', 'indicator', 'prediction_raw',
            'status', 'tie'
        }
        assert set(imrek.keys()) == expected_keys

        # Verify mappings
        assert imrek['fencer_id'] == "425B00719E2740C18ECEC299142D3CF3"
        assert imrek['name'] == "IMREK Elijah S."
        assert imrek['club_primary'] == "University Of Notre Dame NCAA"
        assert imrek['club_secondary'] == "Alliance Fencing Academy"
        assert imrek['division'] == "Gulf Coast"
        assert imrek['country'] == "USA"
        assert imrek['place'] == 1
        assert imrek['victories'] == 6
        assert imrek['matches'] == 6
        assert imrek['victory_ratio'] == 1
        assert imrek['touches_scored'] == 30
        assert imrek['touches_received'] == 9
        assert imrek['indicator'] == 21
        assert imrek['prediction_raw'] == "Advanced"
        assert imrek['status'] == "advanced"
        assert imrek['tie'] is False
