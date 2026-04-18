"""
Itinerary Agent – Tool 2: Budget allocator.

Splits a total trip budget across standard travel categories using
destination-aware cost profiles, then breaks it down per-day.
"""

import json
from langchain_core.tools import tool

# ── Destination cost profiles ────────────────────────────
# Multiplier relative to a "baseline" Western-European city.
# < 1 = cheaper, > 1 = more expensive.
_COST_PROFILES: dict[str, float] = {
    "paris": 1.0,
    "london": 1.15,
    "new york": 1.25,
    "tokyo": 1.05,
    "bangkok": 0.45,
    "bali": 0.40,
    "istanbul": 0.55,
    "rome": 0.90,
    "barcelona": 0.85,
    "berlin": 0.80,
    "dubai": 1.10,
    "sydney": 1.10,
    "cairo": 0.35,
    "mumbai": 0.30,
    "delhi": 0.30,
    "jaipur": 0.28,
    "goa": 0.32,
    "rio de janeiro": 0.55,
    "mexico city": 0.45,
    "lisbon": 0.75,
    "prague": 0.60,
    "amsterdam": 1.00,
    "singapore": 1.10,
    "kuala lumpur": 0.40,
    "hanoi": 0.30,
    "marrakech": 0.40,
    "cape town": 0.50,
    "athens": 0.70,
    "budapest": 0.55,
    "vienna": 0.95,
}

# Base category split (percentages of total budget)
_BASE_SPLIT = {
    "accommodation": 0.35,
    "food_and_dining": 0.25,
    "activities_and_sightseeing": 0.20,
    "local_transport": 0.10,
    "shopping_and_misc": 0.10,
}


def _get_cost_multiplier(destination: str) -> float:
    key = destination.lower().strip()
    for place, mult in _COST_PROFILES.items():
        if place in key or key in place:
            return mult
    return 1.0  # default baseline


@tool
def allocate_budget(
    destination: str,
    total_budget: float,
    currency: str,
    num_days: int,
    travelers: int,
) -> str:
    """Allocate a trip budget across spending categories and per day.

    Adjusts the split based on the destination's relative cost level.
    Use this when building an itinerary to keep activities within budget.

    Args:
        destination: Trip destination city or region.
        total_budget: Maximum total budget amount.
        currency: Budget currency code (e.g. "USD").
        num_days: Number of trip days.
        travelers: Number of travelers sharing the budget.

    Returns:
        JSON with per-category totals, per-day budget, and
        per-person-per-day budget.
    """
    if num_days <= 0 or travelers <= 0 or total_budget <= 0:
        return json.dumps({"error": "num_days, travelers, and total_budget must be > 0"})

    multiplier = _get_cost_multiplier(destination)

    # Adjust split slightly for cheaper destinations
    # (travelers tend to spend proportionally more on activities)
    adjusted_split = {}
    for cat, pct in _BASE_SPLIT.items():
        if cat == "activities_and_sightseeing" and multiplier < 0.6:
            adjusted_split[cat] = pct + 0.05
        elif cat == "accommodation" and multiplier < 0.6:
            adjusted_split[cat] = pct - 0.05
        else:
            adjusted_split[cat] = pct

    categories = {}
    for cat, pct in adjusted_split.items():
        total = round(total_budget * pct, 2)
        categories[cat] = {
            "total": total,
            "per_day": round(total / num_days, 2),
            "per_person_per_day": round(total / num_days / travelers, 2),
        }

    return json.dumps({
        "destination": destination,
        "currency": currency,
        "total_budget": total_budget,
        "cost_level": "budget" if multiplier < 0.5 else "moderate" if multiplier < 0.9 else "high",
        "cost_multiplier": multiplier,
        "num_days": num_days,
        "travelers": travelers,
        "categories": categories,
        "daily_budget": round(total_budget / num_days, 2),
        "daily_per_person": round(total_budget / num_days / travelers, 2),
    }, ensure_ascii=False)
