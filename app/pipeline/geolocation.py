"""
Geolocation normalization and distance-based filtering.

Handles:
  - Canonical location names (e.g., "NYC" → "New York, NY")
  - Fuzzy matching for typos and abbreviations
  - Remote work detection and matching
  - City+State/Country normalization
"""
import logging
import re
from typing import Optional, List, Set

logger = logging.getLogger(__name__)

# ── Canonical US cities (major metros for quick lookup) ──────────────────────
MAJOR_CITIES = {
    # US metros
    "new york": "New York, NY",
    "nyc": "New York, NY",
    "ny": "New York, NY",
    "los angeles": "Los Angeles, CA",
    "la": "Los Angeles, CA",
    "chicago": "Chicago, IL",
    "houston": "Houston, TX",
    "phoenix": "Phoenix, AZ",
    "philadelphia": "Philadelphia, PA",
    "philly": "Philadelphia, PA",
    "san antonio": "San Antonio, TX",
    "san diego": "San Diego, CA",
    "dallas": "Dallas, TX",
    "san francisco": "San Francisco, CA",
    "sf": "San Francisco, CA",
    "sfo": "San Francisco, CA",
    "austin": "Austin, TX",
    "seattle": "Seattle, WA",
    "denver": "Denver, CO",
    "boston": "Boston, MA",
    "miami": "Miami, FL",
    "atlanta": "Atlanta, GA",
    "dc": "Washington, DC",
    "washington": "Washington, DC",
    "portland": "Portland, OR",
    "minneapolis": "Minneapolis, MN",
    "twin cities": "Minneapolis, MN",
    "minneapolis-st. paul": "Minneapolis, MN",
    # Remote
    "remote": "Remote",
    "fully remote": "Remote",
    "work from home": "Remote",
    "wfh": "Remote",
    "anywhere": "Remote",
    "distributed": "Remote",
    # International
    "london": "London, UK",
    "toronto": "Toronto, Canada",
    "vancouver": "Vancouver, Canada",
    "berlin": "Berlin, Germany",
    "singapore": "Singapore",
    "sydney": "Sydney, Australia",
}

# ── US State abbreviations for normalization ──────────────────────────────────
STATE_ABBREV = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}

# ── Reverse mapping for normalization ─────────────────────────────────────────
ABBREV_TO_STATE = {v: k for k, v in STATE_ABBREV.items()}


def normalize_location(location: str) -> str:
    """
    Normalize a location string to a canonical form.

    Examples:
        "NYC" → "New York, NY"
        "san fran" → "San Francisco, CA"
        "remote" → "Remote"
        "Fully Remote, USA" → "Remote"

    Args:
        location: Raw location string (from job posting)

    Returns:
        Normalized location string
    """
    if not location or not isinstance(location, str):
        return ""

    location = location.strip().lower()
    if not location:
        return ""

    # Direct match in major cities
    if location in MAJOR_CITIES:
        return MAJOR_CITIES[location]

    # Check for "Remote" variations
    if any(word in location for word in ["remote", "fully remote", "work from home", "wfh", "anywhere", "distributed"]):
        return "Remote"

    # Fuzzy match: check if location contains a major city as a substring
    for city_key, canonical in MAJOR_CITIES.items():
        if len(city_key) > 3 and city_key in location:  # Avoid matching "LA" in "ATLANTA"
            return canonical

    # Try to parse "City, State" format
    if "," in location:
        parts = [p.strip() for p in location.split(",")]
        if len(parts) >= 2:
            city, state = parts[0], parts[1]
            # Normalize state
            if state.lower() in STATE_ABBREV:
                state = STATE_ABBREV[state.lower()]
            elif state.upper() in STATE_ABBREV.values():
                state = state.upper()
            # Capitalize city
            city = city.title()
            return f"{city}, {state}"
        return location.title()

    # No recognized format; return title-cased
    return location.title()


def is_remote(location: str) -> bool:
    """Check if a location represents remote work."""
    location_lower = location.lower().strip()
    return location_lower in {"remote", "fully remote", "work from home", "wfh", "anywhere", "distributed"}


def location_matches(job_location: str, user_preference: str) -> bool:
    """
    Check if a job location matches a user's geographic preference.

    Rules:
      1. If user preference is empty/None, any job matches (match all)
      2. If user prefers "Remote", only remote jobs match
      3. Exact match (after normalization)
      4. Fuzzy match (city name substring)

    Args:
        job_location: Location from a job posting
        user_preference: User's location preference (or filter)

    Returns:
        True if the job location matches the preference
    """
    if not user_preference or not user_preference.strip():
        # No preference = accept all locations
        return True

    job_loc_norm = normalize_location(job_location)
    user_pref_norm = normalize_location(user_preference)

    # Exact match
    if job_loc_norm == user_pref_norm:
        return True

    # User prefers "Remote": treat as location-flexible (open to anywhere).
    # Real postings are rarely tagged "Remote", so strict remote-only filtering
    # zeroes out the entire job pool — a remote seeker considers nationwide roles.
    if is_remote(user_pref_norm):
        return True

    # A remote job fits ANY location preference (you can do it from anywhere).
    if is_remote(job_loc_norm):
        return True

    # Fuzzy match: if user's preference city appears in job location
    # E.g., user says "California" and job is "San Francisco, CA"
    if user_pref_norm in job_loc_norm:
        return True

    if job_loc_norm in user_pref_norm:
        return True

    # No match
    return False


def get_location_matches(
    locations: List[str],
    user_preference: str,
) -> List[str]:
    """
    Filter a list of job locations by user preference.

    Args:
        locations: List of job locations
        user_preference: User's location filter

    Returns:
        Filtered list of matching locations
    """
    if not user_preference or not user_preference.strip():
        return locations

    return [loc for loc in locations if location_matches(loc, user_preference)]


def extract_unique_locations(locations: List[str]) -> Set[str]:
    """
    Extract and normalize unique locations from a list.

    Args:
        locations: Raw location strings

    Returns:
        Set of normalized, unique locations
    """
    return {normalize_location(loc) for loc in locations if loc}
