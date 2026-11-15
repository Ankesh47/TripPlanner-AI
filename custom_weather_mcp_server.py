import os
from pathlib import Path
from typing import Any

import certifi
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Set SSL Certificate Bundle for Windows
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

mcp = FastMCP("Weather MCP Server")

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
REQUEST_TIMEOUT_SECONDS = 20


def _get_api_key() -> str:
    if not OPENWEATHER_API_KEY:
        raise RuntimeError(
            "OPENWEATHER_API_KEY is missing from the project .env file."
        )
    return OPENWEATHER_API_KEY


def _clean_city_candidates(city: str) -> list[str]:
    """Generate candidate search queries from a raw city/destination string."""
    raw = city.strip().strip("'\"")
    candidates = [raw]

    # Clean leading/trailing noise words like "trip to", "tour", etc.
    cleaned = raw
    prefixes = ["trip to ", "visit to ", "travel to ", "flights to ", "in ", "to "]
    for p in prefixes:
        if cleaned.lower().startswith(p):
            cleaned = cleaned[len(p):].strip()
            break

    suffixes = [" trip", " tour", " vacation", " holiday", " visit", " travel"]
    for s in suffixes:
        if cleaned.lower().endswith(s):
            cleaned = cleaned[:-len(s)].strip()
            break

    if cleaned and cleaned not in candidates:
        candidates.append(cleaned)

    # Handle comma-separated locations (e.g. "Tokyo, Japan" -> "Tokyo")
    if "," in cleaned:
        primary = cleaned.split(",")[0].strip()
        if primary and primary not in candidates:
            candidates.append(primary)

    return candidates


def _request_json(
    url: str,
    city: str,
) -> dict[str, Any]:
    api_key = _get_api_key()
    candidates = _clean_city_candidates(city)

    last_error = None
    for candidate in candidates:
        try:
            response = requests.get(
                url,
                params={
                    "q": candidate,
                    "appid": api_key,
                    "units": "metric",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 404:
                last_error = f"City '{candidate}' not found on OpenWeatherMap."
                continue

            response.raise_for_status()

        except requests.RequestException as exc:
            last_error = f"OpenWeather request error for '{candidate}': {exc}"

    raise RuntimeError(
        last_error or f"Could not retrieve weather data for '{city}'."
    )


@mcp.tool()
def get_current_weather(
    city: str,
) -> dict[str, Any]:
    """Return the current weather for a city."""

    city = city.strip()

    if not city:
        raise ValueError(
            "city cannot be empty"
        )

    data = _request_json(
        "https://api.openweathermap.org/data/2.5/weather",
        city,
    )

    return {
        "city": data["name"],
        "temperature_c": data["main"]["temp"],
        "feels_like_c": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "condition": data["weather"][0]["description"],
        "wind_speed": data["wind"]["speed"],
    }


@mcp.tool()
def get_forecast(
    city: str,
) -> dict[str, Any]:
    """
    Return the first five three-hour
    forecast entries for a city.
    """

    city = city.strip()

    if not city:
        raise ValueError(
            "city cannot be empty"
        )

    data = _request_json(
        "https://api.openweathermap.org/data/2.5/forecast",
        city,
    )

    forecast = [
        {
            "datetime": item["dt_txt"],
            "temperature_c": item["main"]["temp"],
            "condition": item["weather"][0]["description"],
        }
        for item in data.get("list", [])[:5]
    ]

    return {
        "city": data.get(
            "city",
            {},
        ).get(
            "name",
            city,
        ),
        "forecast": forecast,
    }


if __name__ == "__main__":
    # mcp_client.py launches this as a stdio subprocess.
    mcp.run(
        transport="stdio",
    )