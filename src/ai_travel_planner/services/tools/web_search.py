"""
Research Agent – Tool 1 (Mandatory): Serper web search.

Calls the Serper.dev Google Search API and returns a condensed
markdown summary of the top results.
"""

import json
import logging
from typing import Optional

import httpx
from langchain_core.tools import tool

from ai_travel_planner.config.settings import get_settings

logger = logging.getLogger(__name__)

_SERPER_URL = "https://google.serper.dev/search"


async def _call_serper(query: str, num_results: int = 8) -> list[dict]:
    """Low-level async call to the Serper API."""
    settings = get_settings()
    if not settings.serper_api_key:
        logger.warning("SERPER_API_KEY not set – returning empty results")
        return []

    headers = {
        "X-API-KEY": settings.serper_api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": num_results}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_SERPER_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results: list[dict] = []
    for item in data.get("organic", []):
        results.append(
            {
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
            }
        )
    # Include knowledge-graph snippet when available
    kg = data.get("knowledgeGraph", {})
    if kg:
        results.insert(
            0,
            {
                "title": kg.get("title", ""),
                "snippet": kg.get("description", ""),
                "link": "",
            },
        )
    return results


@tool
async def web_search(query: str) -> str:
    """Search the web for real-time information about a travel destination.

    Use this to research attractions, local tips, safety info, visa
    requirements, seasonal considerations, cultural norms, and anything
    else relevant to planning a trip.

    Args:
        query: The search query string.

    Returns:
        A JSON list of search result objects with title, snippet, and link.
    """
    try:
        results = await _call_serper(query)
        if not results:
            return json.dumps(
                [{"title": "No results", "snippet": "Search returned no results.", "link": ""}]
            )
        return json.dumps(results, ensure_ascii=False)
    except Exception as exc:
        logger.exception("Serper search failed for query: %s", query)
        return json.dumps(
            [{"title": "Error", "snippet": f"Search failed: {exc}", "link": ""}]
        )
