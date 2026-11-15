import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import certifi
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient


# =========================================================
# Environment setup
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Support both environment-variable names.
AVIATION_STACK_API_KEY = (
    os.getenv("AVIATION_STACK_API_KEY")
    or os.getenv("AVIATIONSTACK_API_KEY")
)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

WEATHER_SERVER_PATH = BASE_DIR / "custom_weather_mcp_server.py"
UVX_COMMAND = shutil.which("uvx") or "uvx"


def _require_env(name: str, value: str | None) -> str:
    """Return an environment value or raise a readable setup error."""

    if not value:
        raise RuntimeError(
            f"{name} is missing. "
            f"Add {name}=your_key to the project .env file."
        )

    return value


def _subprocess_env(**updates: str | None) -> dict[str, str]:
    """
    Preserve the current Windows/Conda environment and add MCP API keys.
    """

    env = os.environ.copy()

    for key, value in updates.items():
        if value:
            env[key] = value

    return env


# =========================================================
# LLM
# =========================================================

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

llm = ChatGroq(
    model=GROQ_MODEL,
    api_key=_require_env("GROQ_API_KEY", GROQ_API_KEY),
)


# =========================================================
# MCP client
# =========================================================

client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": (
                "https://mcp.tavily.com/mcp/"
                f"?tavilyApiKey={TAVILY_API_KEY or ''}"
            ),
        },

        "aviationstack": {
            "transport": "stdio",
            "command": UVX_COMMAND,
            "args": [
                "aviationstack-mcp",
            ],
            "env": _subprocess_env(
                AVIATION_STACK_API_KEY=AVIATION_STACK_API_KEY,
            ),
        },

        "weather": {
            "transport": "stdio",

            # Uses the Python executable from the active Conda environment.
            "command": sys.executable,

            # Uses the weather server inside the current project folder.
            "args": [
                str(WEATHER_SERVER_PATH),
            ],

            "env": _subprocess_env(
                OPENWEATHER_API_KEY=OPENWEATHER_API_KEY,
            ),
        },
    }
)


async def _get_server_tool(
    server_name: str,
    tool_name: str,
):
    """
    Load one tool from one MCP server.

    This prevents a broken weather or AviationStack server from
    crashing an unrelated Tavily request.
    """

    if server_name == "tavily":
        _require_env(
            "TAVILY_API_KEY",
            TAVILY_API_KEY,
        )

    elif server_name == "aviationstack":
        _require_env(
            "AVIATION_STACK_API_KEY",
            AVIATION_STACK_API_KEY,
        )

        if shutil.which("uvx") is None:
            raise RuntimeError(
                "uvx was not found. Install uv, reopen the terminal, "
                "activate the travel environment, and run "
                "`uvx --version`."
            )

    elif server_name == "weather":
        _require_env(
            "OPENWEATHER_API_KEY",
            OPENWEATHER_API_KEY,
        )

        if not WEATHER_SERVER_PATH.is_file():
            raise FileNotFoundError(
                f"Weather MCP server not found: "
                f"{WEATHER_SERVER_PATH}"
            )

    # Important: load only the requested MCP server.
    tools = await client.get_tools(
        server_name=server_name,
    )

    tool = next(
        (
            item
            for item in tools
            if item.name == tool_name
        ),
        None,
    )

    if tool is None:
        available_tools = (
            ", ".join(
                sorted(item.name for item in tools)
            )
            or "none"
        )

        raise RuntimeError(
            f"MCP tool '{tool_name}' was not found "
            f"on server '{server_name}'. "
            f"Available tools: {available_tools}"
        )

    return tool


# =========================================================
# MCP connection test
# =========================================================

async def get_all_tools() -> None:
    """
    Test every MCP server independently.

    One failed server will not stop the remaining tests.
    """

    for server_name in (
        "tavily",
        "aviationstack",
        "weather",
    ):
        try:
            tools = await client.get_tools(
                server_name=server_name,
            )

            tool_names = (
                ", ".join(
                    tool.name
                    for tool in tools
                )
                or "no tools"
            )

            print(
                f"{server_name}: OK -> {tool_names}"
            )

        except Exception as exc:
            print(
                f"{server_name}: FAILED -> "
                f"{type(exc).__name__}: {exc}"
            )


# =========================================================
# Tavily MCP
# =========================================================

async def tavily_mcp_search(query: str):
    search_tool = await _get_server_tool(
        "tavily",
        "tavily_search",
    )

    return await search_tool.ainvoke(
        {
            "query": query,
        }
    )


# =========================================================
# AviationStack MCP
# =========================================================

async def aviation_mcp_call(
    tool_name: str,
    tool_args: dict[str, Any] | None = None,
):
    aviation_tool = await _get_server_tool(
        "aviationstack",
        tool_name,
    )

    return await aviation_tool.ainvoke(
        tool_args or {}
    )


# =========================================================
# Weather MCP & Result Formatters
# =========================================================

def _extract_text_from_mcp_result(result: Any) -> str:
    """Extract inner text string from an MCP tool return structure."""
    if isinstance(result, list) and result:
        item = result[0]
        if isinstance(item, dict):
            return item.get("text", "")
        return getattr(item, "text", str(item))
    elif isinstance(result, dict):
        return result.get("text", "")
    return str(result)


def _format_weather_result(result: Any, city: str) -> str:
    """Format get_current_weather output into a clean, human-readable summary."""
    text = _extract_text_from_mcp_result(result)

    if not text:
        return f"No weather data returned for {city}."

    if "Error executing tool" in text or "OpenWeather request" in text:
        return f"Weather information for '{city}' could not be retrieved: {text}"

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            c_name = data.get("city", city)
            temp = data.get("temperature_c")
            feels = data.get("feels_like_c")
            cond = data.get("condition", "N/A")
            humidity = data.get("humidity")
            wind = data.get("wind_speed")

            lines = [f"- City: {c_name}"]
            if temp is not None:
                feels_str = f" (Feels like {feels}°C)" if feels is not None else ""
                lines.append(f"- Temperature: {temp}°C{feels_str}")
            if cond:
                lines.append(f"- Condition: {cond.capitalize()}")
            if humidity is not None:
                lines.append(f"- Humidity: {humidity}%")
            if wind is not None:
                lines.append(f"- Wind Speed: {wind} m/s")

            return "\n".join(lines)
    except Exception:
        pass

    return text


def _format_forecast_result(result: Any, city: str) -> str:
    """Format get_forecast output into a clean, human-readable summary."""
    text = _extract_text_from_mcp_result(result)

    if not text:
        return f"No forecast data returned for {city}."

    if "Error executing tool" in text or "OpenWeather request" in text:
        return f"Forecast for '{city}' could not be retrieved: {text}"

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            c_name = data.get("city", city)
            forecast_items = data.get("forecast", [])
            lines = [f"- Location: {c_name}", "- Upcoming Forecast:"]
            for item in forecast_items:
                dt = item.get("datetime", "")
                temp = item.get("temperature_c", "")
                cond = item.get("condition", "").capitalize()
                lines.append(f"  • {dt}: {temp}°C, {cond}")
            return "\n".join(lines)
    except Exception:
        pass

    return text


async def weather_mcp_search(city: str) -> str:
    """Query current weather from Weather MCP and return a formatted string."""
    weather_tool = await _get_server_tool(
        "weather",
        "get_current_weather",
    )

    result = await weather_tool.ainvoke(
        {
            "city": city,
        }
    )

    return _format_weather_result(result, city)


async def forecast_mcp_search(city: str) -> str:
    """Query forecast from Weather MCP and return a formatted string."""
    forecast_tool = await _get_server_tool(
        "weather",
        "get_forecast",
    )

    result = await forecast_tool.ainvoke(
        {
            "city": city,
        }
    )

    return _format_forecast_result(result, city)


# =========================================================
# Destination extractor
# =========================================================

def _extract_destination_fallback(query: str) -> str:
    """Heuristic fallback to extract destination city/country without LLM."""
    q = query.strip()
    # Match "to <destination>"
    match = re.search(
        r"\b(?:to|in|visit)\s+([A-Za-z\s]+?)(?:\s+(?:from|on|for|under|including|with|in|at)\b|[.!?]|$)",
        q,
        re.IGNORECASE,
    )
    if match:
        dest = match.group(1).strip()
        if dest and len(dest) < 40:
            return dest

    # Match "X trip" / "X vacation"
    match = re.search(
        r"([A-Za-z\s]+?)\s+(?:trip|tour|vacation|holiday|travel)",
        q,
        re.IGNORECASE,
    )
    if match:
        words = match.group(1).strip().split()
        # Take the last word before "trip" (e.g. "7 days Japan trip" -> "Japan")
        if words:
            candidate = words[-1].strip()
            if candidate.lower() not in {"days", "day", "nights", "night", "week", "complete", "a", "an", "the"}:
                return candidate

    return "Kolkata"


def extract_destination(query: str) -> str:
    """Extract destination city/country from travel query using LLM with heuristic fallback."""
    q = query.strip()
    try:
        prompt = f"""
Extract only the destination city or country from the travel request.

Travel request:
{q}

Return only the destination name.
Do not add any explanation or punctuation.
"""
        response = llm.invoke(prompt)
        destination = str(response.content).strip().strip("'\".").strip()
        if destination and len(destination) < 50:
            return destination
    except Exception as exc:
        print(
            f"extract_destination LLM notice: {exc}. Using fallback extraction.",
            flush=True,
        )

    return _extract_destination_fallback(q)