"""
Research Agent service.

Runs an LLM-driven ReAct loop with the web_search and weather tools
to produce a comprehensive destination research report.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from ai_travel_planner.config.settings import get_settings
from ai_travel_planner.services.tools.web_search import web_search
from ai_travel_planner.services.tools.weather import get_weather_forecast

logger = logging.getLogger(__name__)

RESEARCH_TOOLS = [web_search, get_weather_forecast]

_SYSTEM_PROMPT = """\
You are a world-class travel research analyst. Given a travel request,
use your tools to gather comprehensive destination intelligence.

You MUST call the web_search tool at least twice — once for general
destination info (attractions, tips, safety) and once for seasonal /
event-specific information. Also call get_weather_forecast for the
destination.

Produce a structured research report in **JSON** with these keys:
{
  "destination_overview": "...",
  "top_attractions": ["..."],
  "local_tips": ["..."],
  "safety_info": "...",
  "weather_summary": "...",
  "seasonal_notes": "...",
  "cultural_norms": "...",
  "transportation_options": "...",
  "estimated_daily_costs": "..."
}
Return ONLY the JSON object — no markdown fences, no commentary.
"""


async def _execute_tool(tool_call: dict) -> str:
    """Dispatch a tool call by name."""
    name = tool_call["name"]
    args = tool_call["args"]
    for t in RESEARCH_TOOLS:
        if t.name == name:
            return await t.ainvoke(args)
    return json.dumps({"error": f"Unknown tool: {name}"})


async def run_research_agent(state: dict[str, Any]) -> str:
    """Run the research agent and return the research report (JSON string).

    The agent performs a multi-turn tool-calling loop until the LLM
    produces a final answer (no more tool calls).
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=settings.openai_temperature,
    )
    llm_with_tools = llm.bind_tools(RESEARCH_TOOLS)

    user_prompt = (
        f"Research the destination: {state['destination']}\n"
        f"Travel dates: {state['start_date']} to {state['end_date']}\n"
        f"Travelers: {state['travelers']}\n"
        f"Interests: {', '.join(state.get('interests') or ['general sightseeing'])}\n"
        f"Budget: {state['budget_currency']} {state['budget_min']}-{state['budget_max']}\n"
    )

    messages: list = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    max_iterations = 8
    for _ in range(max_iterations):
        response: AIMessage = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            # Final answer
            logger.info("Research agent finished with %d messages", len(messages))
            return response.content

        # Execute every tool call the LLM requested
        for tc in response.tool_calls:
            logger.info("Research agent calling tool: %s", tc["name"])
            result = await _execute_tool(tc)
            messages.append(
                ToolMessage(content=result, tool_call_id=tc["id"])
            )

    # Safety: if we exhaust iterations, return whatever we have
    logger.warning("Research agent hit max iterations")
    return messages[-1].content if hasattr(messages[-1], "content") else "{}"
