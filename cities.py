"""
Curated list of major world cities tracked by the advisor.
Add more any time -- ingest.py will pick up new entries automatically
(it upserts this list into the `cities` table on every run).

`tz` is the city's IANA time zone name (e.g. "America/Chicago"). Data is
always fetched and stored in UTC (see ingest.py / schema.sql) -- `tz` is
used only at display time in app.py, to show each city's own local time
instead of a UTC timestamp nobody thinks in day to day.
"""

CITIES = [
    # North America
    {"name": "Chicago", "country": "USA", "lat": 41.8781, "lon": -87.6298, "tz": "America/Chicago"},
    {"name": "New York", "country": "USA", "lat": 40.7128, "lon": -74.0060, "tz": "America/New_York"},
    {"name": "Los Angeles", "country": "USA", "lat": 34.0522, "lon": -118.2437, "tz": "America/Los_Angeles"},
    {"name": "San Francisco", "country": "USA", "lat": 37.7749, "lon": -122.4194, "tz": "America/Los_Angeles"},
    {"name": "Seattle", "country": "USA", "lat": 47.6062, "lon": -122.3321, "tz": "America/Los_Angeles"},
    {"name": "Austin", "country": "USA", "lat": 30.2672, "lon": -97.7431, "tz": "America/Chicago"},
    {"name": "Miami", "country": "USA", "lat": 25.7617, "lon": -80.1918, "tz": "America/New_York"},
    {"name": "Denver", "country": "USA", "lat": 39.7392, "lon": -104.9903, "tz": "America/Denver"},
    {"name": "Toronto", "country": "Canada", "lat": 43.6532, "lon": -79.3832, "tz": "America/Toronto"},
    {"name": "Vancouver", "country": "Canada", "lat": 49.2827, "lon": -123.1207, "tz": "America/Vancouver"},
    {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lon": -99.1332, "tz": "America/Mexico_City"},
    # South America
    {"name": "Sao Paulo", "country": "Brazil", "lat": -23.5505, "lon": -46.6333, "tz": "America/Sao_Paulo"},
    {"name": "Buenos Aires", "country": "Argentina", "lat": -34.6037, "lon": -58.3816, "tz": "America/Argentina/Buenos_Aires"},
    {"name": "Bogota", "country": "Colombia", "lat": 4.7110, "lon": -74.0721, "tz": "America/Bogota"},
    {"name": "Lima", "country": "Peru", "lat": -12.0464, "lon": -77.0428, "tz": "America/Lima"},
    # Europe
    {"name": "London", "country": "UK", "lat": 51.5074, "lon": -0.1278, "tz": "Europe/London"},
    {"name": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522, "tz": "Europe/Paris"},
    {"name": "Berlin", "country": "Germany", "lat": 52.5200, "lon": 13.4050, "tz": "Europe/Berlin"},
    {"name": "Madrid", "country": "Spain", "lat": 40.4168, "lon": -3.7038, "tz": "Europe/Madrid"},
    {"name": "Rome", "country": "Italy", "lat": 41.9028, "lon": 12.4964, "tz": "Europe/Rome"},
    {"name": "Amsterdam", "country": "Netherlands", "lat": 52.3676, "lon": 4.9041, "tz": "Europe/Amsterdam"},
    {"name": "Stockholm", "country": "Sweden", "lat": 59.3293, "lon": 18.0686, "tz": "Europe/Stockholm"},
    {"name": "Warsaw", "country": "Poland", "lat": 52.2297, "lon": 21.0122, "tz": "Europe/Warsaw"},
    {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lon": 37.6173, "tz": "Europe/Moscow"},
    {"name": "Istanbul", "country": "Turkey", "lat": 41.0082, "lon": 28.9784, "tz": "Europe/Istanbul"},
    # Africa
    {"name": "Cairo", "country": "Egypt", "lat": 30.0444, "lon": 31.2357, "tz": "Africa/Cairo"},
    {"name": "Lagos", "country": "Nigeria", "lat": 6.5244, "lon": 3.3792, "tz": "Africa/Lagos"},
    {"name": "Nairobi", "country": "Kenya", "lat": -1.2921, "lon": 36.8219, "tz": "Africa/Nairobi"},
    {"name": "Johannesburg", "country": "South Africa", "lat": -26.2041, "lon": 28.0473, "tz": "Africa/Johannesburg"},
    {"name": "Casablanca", "country": "Morocco", "lat": 33.5731, "lon": -7.5898, "tz": "Africa/Casablanca"},
    # Middle East
    {"name": "Dubai", "country": "UAE", "lat": 25.2048, "lon": 55.2708, "tz": "Asia/Dubai"},
    {"name": "Tel Aviv", "country": "Israel", "lat": 32.0853, "lon": 34.7818, "tz": "Asia/Jerusalem"},
    {"name": "Riyadh", "country": "Saudi Arabia", "lat": 24.7136, "lon": 46.6753, "tz": "Asia/Riyadh"},
    # South & East Asia
    {"name": "Mumbai", "country": "India", "lat": 19.0760, "lon": 72.8777, "tz": "Asia/Kolkata"},
    {"name": "Delhi", "country": "India", "lat": 28.7041, "lon": 77.1025, "tz": "Asia/Kolkata"},
    {"name": "Ahmedabad", "country": "India", "lat": 23.0225, "lon": 72.5714, "tz": "Asia/Kolkata"},
    {"name": "Bangalore", "country": "India", "lat": 12.9716, "lon": 77.5946, "tz": "Asia/Kolkata"},
    {"name": "Dhaka", "country": "Bangladesh", "lat": 23.8103, "lon": 90.4125, "tz": "Asia/Dhaka"},
    {"name": "Karachi", "country": "Pakistan", "lat": 24.8607, "lon": 67.0011, "tz": "Asia/Karachi"},
    {"name": "Beijing", "country": "China", "lat": 39.9042, "lon": 116.4074, "tz": "Asia/Shanghai"},
    {"name": "Shanghai", "country": "China", "lat": 31.2304, "lon": 121.4737, "tz": "Asia/Shanghai"},
    {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503, "tz": "Asia/Tokyo"},
    {"name": "Seoul", "country": "South Korea", "lat": 37.5665, "lon": 126.9780, "tz": "Asia/Seoul"},
    {"name": "Bangkok", "country": "Thailand", "lat": 13.7563, "lon": 100.5018, "tz": "Asia/Bangkok"},
    {"name": "Singapore", "country": "Singapore", "lat": 1.3521, "lon": 103.8198, "tz": "Asia/Singapore"},
    {"name": "Jakarta", "country": "Indonesia", "lat": -6.2088, "lon": 106.8456, "tz": "Asia/Jakarta"},
    {"name": "Manila", "country": "Philippines", "lat": 14.5995, "lon": 120.9842, "tz": "Asia/Manila"},
    # Oceania
    {"name": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093, "tz": "Australia/Sydney"},
    {"name": "Melbourne", "country": "Australia", "lat": -37.8136, "lon": 144.9631, "tz": "Australia/Melbourne"},
    {"name": "Auckland", "country": "New Zealand", "lat": -36.8485, "lon": 174.7633, "tz": "Pacific/Auckland"},
]
