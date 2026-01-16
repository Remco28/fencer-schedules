"""Parser package for FTL data extraction."""
from .pool_ids import parse_pool_ids
from .pools import parse_pool_html
from .pool_results import parse_pool_results
from .de_tableau import parse_de_tableau
from .tournament_schedule import parse_tournament_schedule
from .event_rounds import parse_event_rounds

__all__ = [
    "parse_pool_ids",
    "parse_pool_html",
    "parse_pool_results",
    "parse_de_tableau",
    "parse_tournament_schedule",
    "parse_event_rounds",
]
