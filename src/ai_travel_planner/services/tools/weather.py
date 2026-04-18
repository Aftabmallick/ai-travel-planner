"""
Research Agent – Tool 2: Weather forecast via Open-Meteo (free, no key).

Fetches a 16-day forecast for a given location using the free
Open-Meteo Forecast API and the Open-Meteo Geocoding API to
resolve destination names to coordinates.
"""

import json
import logging
from typing import Optional

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


async def _geocode(place: str) -> Optional[dict]:
    """Resolve a place name to lat/lon via Open-Meteo geocoding."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_GEOCODE_URL, params={"name": place, "count": 1})
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return {
                "lat": results[0]["latitude"],
                "lon": results[0]["longitude"],
                "name": results[0].get("name", place),
                "country": results[0].get("country", ""),
            }
    return None


async def _fetch_forecast(lat: float, lon: float) -> dict:
    """Fetch daily forecast from Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
        "timezone": "auto",
        "forecast_days": 16,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_FORECAST_URL, params=params)
        resp.raise_for_status()
        return resp.json()


# WMO weather-code → human-readable description (subset)
_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def _format_forecast(raw: dict, place_info: dict) -> list[dict]:
    daily = raw.get("daily", {})
    dates = daily.get("time", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    codes = daily.get("weathercode", [])

    days = []
    for i, d in enumerate(dates):
        days.append({
            "date": d,
            "high_c": t_max[i] if i < len(t_max) else None,
            "low_c": t_min[i] if i < len(t_min) else None,
            "precipitation_mm": precip[i] if i < len(precip) else None,
            "condition": _WMO_CODES.get(codes[i], "Unknown") if i < len(codes) else "Unknown",
        })
    return days


@tool
async def get_weather_forecast(destination: str) -> str:
    """Get the 16-day weather forecast for a travel destination.

    Useful for advising travelers on what to pack and which days are
    best for outdoor activities.

    Args:
        destination: Name of the city or region (e.g. "Paris, France").

    Returns:
        JSON array of daily forecast objects with date, temperatures,
        precipitation, and weather condition.
    """
    try:
        geo = await _geocode(destination)
        if geo is None:
            return json.dumps({"error": f"Could not geocode '{destination}'"})

        raw = await _fetch_forecast(geo["lat"], geo["lon"])
        forecast = _format_forecast(raw, geo)
        return json.dumps(
            {"location": geo, "forecast": forecast},
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.exception("Weather lookup failed for %s", destination)
        return json.dumps({"error": f"Weather lookup failed: {exc}"})
