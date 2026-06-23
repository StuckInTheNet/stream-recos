from scrapers.netflix import NetflixScraper
from scrapers.disney import DisneyScraper
from scrapers.hulu import HuluScraper
from scrapers.max import MaxScraper

SCRAPERS = {
    "netflix": NetflixScraper,
    "disney": DisneyScraper,
    "hulu": HuluScraper,
    "max": MaxScraper,
}
