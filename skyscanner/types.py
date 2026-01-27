from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

@dataclass
class Location:
    """
    Represents an auto-suggested location from the Skyscanner API.

    Attributes:
        entity_name (str): Human-readable name of the location.
        entity_id (str): Internal Skyscanner identifier for the location.
        location (list[str]): Latitude and longitude as strings, split from the raw API response.
    """
    entity_name: str
    entity_id: str
    _raw_location: str = field(repr=False)

    # this field is populated in __post_init__ by splitting _raw_location
    location: list[str] = field(init=False)

    def __post_init__(self):
        # split the raw "lat,lng" string into ['lat', 'lng']
        self.location = self._raw_location.split(",")

@dataclass(frozen=True)
class Airport:
    """
    Represents an airport, city or country in the Skyscanner system.

    Attributes:
        title (str): The display name (e.g. "London Heathrow").
        entity_id (str): The internal Skyscanner entity ID.
        skyId (str): The IATA-style Skyscanner identifier (used in search requests).
        entity_type (str): Type of entity - "AIRPORT", "CITY", "COUNTRY" or empty string.
        subtitle (str): Additional info like country name.
    """
    title: str
    entity_id: str
    skyId: str
    entity_type: str = ""  # AIRPORT, CITY, COUNTRY
    subtitle: str = ""

@dataclass
class SkyscannerResponse:
    """
    Represents the response from a Skyscanner flight search.

    Attributes:
        data (dict): The raw JSON response returned by Skyscanner.
        session_id (str): The unique session identifier associated with the search.
        search_payload (dict): The original payload used to perform the search request.
        origin (Airport): The airport from which the search was initiated.
        destination (Optional[Airport]): The destination airport, if specified.
    """
    json: dict
    session_id: str
    search_payload: dict
    origin: Airport
    destination: Optional[Airport] = None

@dataclass
class Coordinates:
    latitude: float
    longitude: float 

class CabinClass(Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"

class SpecialTypes(Enum):
    ANYTIME = "anytime"
    EVERYWHERE = "everywhere"

