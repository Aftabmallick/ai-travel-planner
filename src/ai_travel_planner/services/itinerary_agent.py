"""
Itinerary Planner Agent service.

Takes the research data and user request, then uses the distance
calculator and budget allocator tools to build a structured
day-by-day itinerary that respects time and budget constraints.
"""

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from ai_travel_planner.config.settings import get_settings
from ai_travel_planner.services.tools.distance_calculator import calculate_distance
from ai_travel_planner.services.tools.budget_allocator import allocate_budget

logger = logging.getLogger(__name__)

ITINERARY_TOOLS = [calculate_distance, allocate_budget]

_SYSTEM_PROMPT = """\
You are an expert travel itinerary planner. You receive destination
research and trip parameters, and you must build a detailed day-by-day
itinerary.

RULES:
1. Call allocate_budget ONCE to understand spending limits.
2. The calculate_distance tool is OPTIONAL — only use it once or
   twice at most to sanity-check distances. If the tool returns a
   "note" saying coordinates are unavailable, do NOT retry it.
   Just assume a typical intra-city distance and move on.
3. After at most 2 tool-call rounds, STOP calling tools and produce
   the final itinerary JSON directly.
4. Produce the final itinerary as a **JSON object** with exactly this
   structure (no markdown fences, no extra commentary):

{
  "destination": "<city/region>",
  "days": [
    {
      "day": 1,
      "date": "YYYY-MM-DD",
      "activities": [
        {
          "time": "09:00",
          "title": "Activity name",
          "description": "Brief description",
          "location": "Place name",
          "estimated_cost": 25.00
        }
      ]
    }
  ]
}

Include 3-5 activities per day. Each activity must have realistic
estimated_cost values that fit within the daily budget. Use the
research data to choose the best attractions and experiences for the
traveler's interests.

Return ONLY the JSON object.
"""


def _execute_tool_sync(tool_call: dict) -> str:
    """Dispatch a tool call by name. Both tools are synchronous."""
    name = tool_call["name"]
    args = tool_call["args"]
    for t in ITINERARY_TOOLS:
        if t.name == name:
            return t.invoke(args)
    return json.dumps({"error": f"Unknown tool: {name}"})


async def run_itinerary_agent(state: dict[str, Any]) -> dict:
    """Run the itinerary planner and return a parsed itinerary dict.

    Returns the itinerary dict matching the Itinerary schema structure.
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=settings.openai_temperature,
    )
    llm_with_tools = llm.bind_tools(ITINERARY_TOOLS)
    # Plain LLM (no tools) for the forced-finish call
    llm_plain = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=settings.openai_temperature,
    )

    # Build the user prompt with all context
    research_data = state.get("research_data", "{}")
    revision_context = ""
    if state.get("review_comments"):
        revision_context = (
            f"\n\nThe user rejected the previous itinerary with this feedback:\n"
            f"{state['review_comments']}\n"
        )
    if state.get("review_modifications"):
        revision_context += (
            f"\nSpecific modifications requested:\n"
            f"{json.dumps(state['review_modifications'], indent=2)}\n"
        )
    if state.get("draft_itinerary") and revision_context:
        revision_context += (
            f"\nPrevious itinerary (to revise):\n"
            f"{json.dumps(state['draft_itinerary'], indent=2)}\n"
        )

    user_prompt = (
        f"Create a day-by-day itinerary for:\n"
        f"  Destination: {state['destination']}\n"
        f"  Dates: {state['start_date']} to {state['end_date']}\n"
        f"  Travelers: {state['travelers']}\n"
        f"  Interests: {', '.join(state.get('interests') or ['general'])}\n"
        f"  Budget: {state['budget_currency']} {state['budget_min']}-{state['budget_max']}\n"
        f"\nResearch data:\n{research_data}\n"
        f"{revision_context}"
    )

    messages: list = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    max_iterations = 6
    final_content = ""

    for iteration in range(max_iterations):
        response: AIMessage = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            # LLM produced a final answer — done
            final_content = response.content
            logger.info(
                "Itinerary agent finished with %d messages (iteration %d)",
                len(messages), iteration,
            )
            break

        # Execute tool calls
        for tc in response.tool_calls:
            logger.info("Itinerary agent calling tool: %s", tc["name"])
            result = _execute_tool_sync(tc)
            messages.append(
                ToolMessage(content=str(result), tool_call_id=tc["id"])
            )
    else:
        # Exhausted iterations — force a final answer without tools
        logger.warning(
            "Itinerary agent hit max iterations (%d), forcing final answer",
            max_iterations,
        )
        messages.append({
            "role": "user",
            "content": (
                "You have used enough tools. STOP calling tools now. "
                "Produce the final itinerary JSON immediately based on "
                "all the information you already have."
            ),
        })
        forced_response: AIMessage = await llm_plain.ainvoke(messages)
        final_content = forced_response.content
        logger.info("Itinerary agent produced forced final answer")

    # Parse the final response as JSON
    try:
        cleaned = final_content.strip()
        if cleaned.startswith("```"):
            # Strip markdown fences like ```json ... ```
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        itinerary = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError, AttributeError):
        logger.error("Failed to parse itinerary JSON, returning raw content")
        itinerary = {
            "destination": state["destination"],
            "days": [],
            "_raw": final_content,
        }

    return itinerary
