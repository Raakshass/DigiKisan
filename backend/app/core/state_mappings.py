"""
KisanMitra AI — State & District Mappings
=======================================
Master reference for all location data used in:
- Data ingestion (which states/districts to scrape)
- RAG search (location-based filtering)
- ChatOrchestrator (user location → state resolution)

Sources:
- ICAR-CRIDA portal state IDs
- IMD state codes
- Census 2011 district names (standardized)
"""
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# State Configuration
# ---------------------------------------------------------------------------
STATE_CONFIG: Dict[str, Dict] = {
    "UP": {
        "full_name": "Uttar Pradesh",
        "lang": "hi",
        "crida_state_param": "Uttar+Pradesh",
        "major_crops": ["wheat", "rice", "sugarcane", "mustard", "potato"],
        "seasons": {"rabi": "Oct-Mar", "kharif": "Jun-Oct", "zaid": "Mar-Jun"},
        "key_districts": [
            "Lucknow", "Varanasi", "Agra", "Allahabad", "Kanpur",
            "Gorakhpur", "Meerut", "Bareilly", "Moradabad", "Aligarh",
            "Jhansi", "Mathura", "Ayodhya", "Sultanpur", "Barabanki",
        ],
        "state_portal": "https://upagripardarshi.gov.in",
        "lat_lon": (26.85, 80.91),  # Lucknow center
    },
    "MP": {
        "full_name": "Madhya Pradesh",
        "lang": "hi",
        "crida_state_param": "Madhya+Pradesh",
        "major_crops": ["wheat", "soybean", "gram", "rice", "maize"],
        "seasons": {"rabi": "Oct-Mar", "kharif": "Jun-Oct"},
        "key_districts": [
            "Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain",
            "Sagar", "Dewas", "Satna", "Rewa", "Hoshangabad",
            "Vidisha", "Raisen", "Sehore", "Chhindwara", "Betul",
        ],
        "state_portal": "https://mpkrishi.mp.gov.in",
        "lat_lon": (23.26, 77.41),  # Bhopal center
    },
    "MH": {
        "full_name": "Maharashtra",
        "lang": "mr",
        "crida_state_param": "Maharashtra",
        "major_crops": ["sugarcane", "cotton", "soybean", "rice", "jowar"],
        "seasons": {"rabi": "Oct-Mar", "kharif": "Jun-Oct"},
        "key_districts": [
            "Pune", "Nashik", "Nagpur", "Aurangabad", "Solapur",
            "Kolhapur", "Satara", "Sangli", "Ahmednagar", "Jalgaon",
            "Beed", "Latur", "Osmanabad", "Buldhana", "Yavatmal",
        ],
        "state_portal": "https://krishi.maharashtra.gov.in",
        "lat_lon": (19.08, 72.88),  # Mumbai center
    },
    "PB": {
        "full_name": "Punjab",
        "lang": "pa",
        "crida_state_param": "Punjab",
        "major_crops": ["wheat", "rice", "cotton", "maize", "sugarcane"],
        "seasons": {"rabi": "Oct-Apr", "kharif": "Jun-Oct"},
        "key_districts": [
            "Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda",
            "Mohali", "Sangrur", "Moga", "Ferozepur", "Hoshiarpur",
            "Gurdaspur", "Kapurthala", "Faridkot", "Mansa", "Muktsar",
        ],
        "state_portal": "https://agripb.gov.in",
        "lat_lon": (30.90, 75.86),  # Ludhiana center
    },
    "KA": {
        "full_name": "Karnataka",
        "lang": "kn",
        "crida_state_param": "Karnataka",
        "major_crops": ["rice", "ragi", "jowar", "maize", "sugarcane", "coffee"],
        "seasons": {"rabi": "Oct-Mar", "kharif": "Jun-Oct"},
        "key_districts": [
            "Bengaluru", "Mysuru", "Belgaum", "Hubli-Dharwad", "Mangalore",
            "Shimoga", "Bellary", "Davangere", "Gulbarga", "Raichur",
            "Bijapur", "Hassan", "Mandya", "Tumkur", "Chitradurga",
        ],
        "state_portal": "https://raitamitra.kar.nic.in",
        "lat_lon": (12.97, 77.59),  # Bengaluru center
    },
}


# ---------------------------------------------------------------------------
# Location Resolution
# ---------------------------------------------------------------------------
# Fuzzy mapping of common location strings to state codes
_LOCATION_ALIASES: Dict[str, str] = {}


def _build_alias_map():
    """Build reverse lookup: city/district name → state code."""
    for code, cfg in STATE_CONFIG.items():
        # State full name
        _LOCATION_ALIASES[cfg["full_name"].lower()] = code
        # State code itself
        _LOCATION_ALIASES[code.lower()] = code
        # All districts
        for d in cfg["key_districts"]:
            _LOCATION_ALIASES[d.lower()] = code


_build_alias_map()


def resolve_state(location: Optional[str]) -> Optional[str]:
    """
    Resolve a user-provided location string to a state code.

    Examples:
        "Lucknow" → "UP"
        "Uttar Pradesh" → "UP"
        "Pune, Maharashtra" → "MH"
        "unknown" → None

    Returns None if location can't be resolved (graceful degradation).
    """
    if not location:
        return None

    location_lower = location.lower().strip()

    # Direct match
    if location_lower in _LOCATION_ALIASES:
        return _LOCATION_ALIASES[location_lower]

    # Try each word (handles "Lucknow, UP" or "Lucknow Uttar Pradesh")
    for word in location_lower.replace(",", " ").split():
        word = word.strip()
        if word in _LOCATION_ALIASES:
            return _LOCATION_ALIASES[word]

    return None


def get_state_config(state_code: str) -> Optional[Dict]:
    """Get full config for a state code. Returns None if unknown."""
    return STATE_CONFIG.get(state_code.upper())


def get_all_state_codes() -> List[str]:
    """Get list of all configured state codes."""
    return list(STATE_CONFIG.keys())
