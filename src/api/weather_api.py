import requests
import os
import dotenv
import logging

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


def get_weather():
    """Fetch weather forecast data from the Open-Meteo API via GET request."""

    url = os.getenv("WEATHER_API_URL")
    if not url:
        raise ValueError("WEATHER_API_URL environment variable is not set.")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("Weather API request timed out after 30 seconds.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Weather API returned an error.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Weather API request failed: {e}")

    data = response.json()

    if "hourly" not in data:
        raise ValueError(
            f"Unexpected API response structure. Keys found: {list(data.keys())}"
        )

    logger.info(
        "Successfully fetched weather data with %d hourly records.",
        len(data["hourly"].get("time", [])),
    )
    return data
