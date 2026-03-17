"""State DOE superintendent directory scrapers."""

from scrapers.states.california import CaliforniaScraper
from scrapers.states.florida import FloridaScraper
from scrapers.states.illinois import IllinoisScraper
from scrapers.states.new_york import NewYorkScraper
from scrapers.states.texas import TexasScraper

SCRAPERS = {
    "FL": FloridaScraper,
    "CA": CaliforniaScraper,
    "TX": TexasScraper,
    "NY": NewYorkScraper,
    "IL": IllinoisScraper,
}

__all__ = [
    "SCRAPERS",
    "FloridaScraper",
    "CaliforniaScraper",
    "TexasScraper",
    "NewYorkScraper",
    "IllinoisScraper",
]
