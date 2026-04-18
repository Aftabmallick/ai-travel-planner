"""
LangGraph workflow – the orchestrator.

Defines a StateGraph that moves through:
  intake → research → plan_itinerary → hitl_review → finalize
with conditional routing back for revisions.

The HITL interrupt uses LangGraph's ``interrupt()`` primitive so that
workflow state is persisted in the checkpointer across the pause.
"""

import json
import logging
from datetime import date, timedelta
from typing import Any, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ai_travel_planner.config.settings import get_settings
from ai_travel_planner.repository.plan_repository import PlanRepository
from ai_travel_planner.services.research_agent import run_research_agent
from ai_travel_planner.services.itinerary_agent import run_itinerary_agent

logger = logging.getLogger(__name__)


# ─── Workflow state schema ───────────────────────────────
class TravelPlanState(TypedDict, total=False):
    """State that flows through every node of the graph."""
    # Input fields
    plan_id: str
    destination: str
    start_date: str
    end_date: str
    budget_min: float
    budget_max: float
    budget_currency: str
    interests: list[str]
    travelers: int

    # Workflow tracking
    status: str
    stage: str

    # Agent outputs
    research_data: str
    draft_itinerary: dict

    # HITL feedback
    review_action: str
    review_comments: str
    review_modifications: dict

    # Final output
    final_itinerary: dict

    # Meta
    error: str
    revision_count: int


# ─── Workflow service ────────────────────────────────────
class WorkflowService:
    """Builds and manages the LangGraph travel-planning workflow."""

    def __init__(self, repo: PlanRepository) -> None:
        self.repo = repo
        self.checkpointer = MemorySaver()
        self.graph = self._build_graph()

    # ── graph construction ───────────────────────────────
    def _build_graph(self) -> Any:
        builder = StateGraph(TravelPlanState)

        # Register nodes
        builder.add_node("validate_input", self._validate_input)
        builder.add_node("research", self._research)
        builder.add_node("plan_itinerary", self._plan_itinerary)
        builder.add_node("hitl_review", self._hitl_review)
        builder.add_node("handle_feedback", self._handle_feedback)
        builder.add_node("finalize", self._finalize)

        # Edges
        builder.add_edge(START, "validate_input")
        builder.add_edge("validate_input", "research")
        builder.add_edge("research", "plan_itinerary")
        builder.add_edge("plan_itinerary", "hitl_review")
        builder.add_edge("hitl_review", "handle_feedback")

        # Conditional routing after feedback
        builder.add_conditional_edges(
            "handle_feedback",
            self._route_after_feedback,
            {
                "finalize": "finalize",
                "research": "research",
            },
        )
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self.checkpointer)

    # ── node implementations ─────────────────────────────
    async def _validate_input(self, state: TravelPlanState) -> dict:
        """Validate the travel request and transition to research."""
        plan_id = state["plan_id"]
        await self.repo.update(plan_id, status="pending", stage="intake")

        # Basic validation
        errors = []
        if not state.get("destination"):
            errors.append("destination is required")
        if not state.get("start_date") or not state.get("end_date"):
            errors.append("start_date and end_date are required")
        if state.get("budget_min", 0) > state.get("budget_max", 0):
            errors.append("budget min must be <= max")

        if errors:
            error_msg = "; ".join(errors)
            await self.repo.update(plan_id, status="failed", error=error_msg)
            return {"status": "failed", "error": error_msg}

        return {"status": "researching", "stage": "research", "revision_count": 0}

    async def _research(self, state: TravelPlanState) -> dict:
        """Run the Research Agent."""
        plan_id = state["plan_id"]
        await self.repo.update(plan_id, status="researching", stage="research")

        try:
            research_data = await run_research_agent(state)
            await self.repo.update(plan_id, research_data=research_data)
            return {
                "research_data": research_data,
                "status": "planning",
                "stage": "itinerary_generation",
            }
        except Exception as exc:
            logger.exception("Research agent failed for plan %s", plan_id)
            error_msg = f"Research failed: {exc}"
            await self.repo.update(plan_id, status="failed", error=error_msg)
            return {"status": "failed", "error": error_msg}

    async def _plan_itinerary(self, state: TravelPlanState) -> dict:
        """Run the Itinerary Planner Agent."""
        plan_id = state["plan_id"]
        await self.repo.update(plan_id, status="planning", stage="itinerary_generation")

        try:
            itinerary = await run_itinerary_agent(state)
            await self.repo.update(plan_id, draft_itinerary=itinerary)
            return {
                "draft_itinerary": itinerary,
                "status": "awaiting_review",
                "stage": "hitl_review",
            }
        except Exception as exc:
            logger.exception("Itinerary agent failed for plan %s", plan_id)
            error_msg = f"Planning failed: {exc}"
            await self.repo.update(plan_id, status="failed", error=error_msg)
            return {"status": "failed", "error": error_msg}

    async def _hitl_review(self, state: TravelPlanState) -> dict:
        """Pause execution for human review using LangGraph interrupt.

        The interrupt() call persists the state and pauses the graph.
        When the API resumes with Command(resume=feedback), the
        interrupt() call returns that feedback value.
        """
        plan_id = state["plan_id"]
        await self.repo.update(
            plan_id,
            status="awaiting_review",
            stage="hitl_review",
            draft_itinerary=state.get("draft_itinerary"),
        )

        # ── INTERRUPT ── graph pauses here ──
        feedback = interrupt(
            {
                "message": "Draft itinerary ready for review",
                "plan_id": plan_id,
                "draft_itinerary": state.get("draft_itinerary"),
            }
        )

        # Execution resumes here after Command(resume=...) with the
        # user's review payload
        return {
            "review_action": feedback.get("action", "approve"),
            "review_comments": feedback.get("comments", ""),
            "review_modifications": feedback.get("modifications", {}),
        }

    async def _handle_feedback(self, state: TravelPlanState) -> dict:
        """Process the HITL feedback and prepare for routing."""
        plan_id = state["plan_id"]
        action = state.get("review_action", "approve")

        if action == "approve":
            await self.repo.update(plan_id, status="approved", stage="finalized")
            return {"status": "approved", "stage": "finalized"}

        # reject or modify → route back to revision
        revision_count = state.get("revision_count", 0) + 1
        settings = get_settings()

        if revision_count > settings.max_revisions:
            await self.repo.update(
                plan_id, status="failed",
                error=f"Max revisions ({settings.max_revisions}) exceeded",
            )
            return {
                "status": "failed",
                "error": f"Max revisions ({settings.max_revisions}) exceeded",
            }

        await self.repo.update(
            plan_id, status="revising", stage="revision",
            revision_count=revision_count,
        )
        return {
            "status": "revising",
            "stage": "revision",
            "revision_count": revision_count,
        }

    async def _finalize(self, state: TravelPlanState) -> dict:
        """Produce the final approved itinerary."""
        plan_id = state["plan_id"]
        final = state.get("draft_itinerary", {})
        await self.repo.update(
            plan_id,
            status="approved",
            stage="finalized",
            final_itinerary=final,
        )
        return {
            "final_itinerary": final,
            "status": "approved",
            "stage": "finalized",
        }

    # ── conditional edge ─────────────────────────────────
    @staticmethod
    def _route_after_feedback(state: TravelPlanState) -> str:
        if state.get("status") == "approved":
            return "finalize"
        if state.get("status") == "failed":
            return "finalize"  # will just persist the error
        return "research"  # re-run full pipeline for revisions

    # ── public API ───────────────────────────────────────
    async def start_workflow(self, plan_id: str, request_data: dict) -> None:
        """Kick off the workflow — runs until the HITL interrupt."""
        initial_state: TravelPlanState = {
            "plan_id": plan_id,
            "destination": request_data["destination"],
            "start_date": str(request_data["start_date"]),
            "end_date": str(request_data["end_date"]),
            "budget_min": request_data["budget"]["min"],
            "budget_max": request_data["budget"]["max"],
            "budget_currency": request_data["budget"]["currency"],
            "interests": request_data.get("interests") or [],
            "travelers": request_data["travelers"],
            "status": "pending",
            "stage": "intake",
            "research_data": "",
            "draft_itinerary": {},
            "review_action": "",
            "review_comments": "",
            "review_modifications": {},
            "final_itinerary": {},
            "error": "",
            "revision_count": 0,
        }

        config = {"configurable": {"thread_id": plan_id}}
        try:
            await self.graph.ainvoke(initial_state, config)
        except Exception as exc:
            logger.exception("Workflow failed for plan %s", plan_id)
            await self.repo.update(plan_id, status="failed", error=str(exc))

    async def resume_workflow(self, plan_id: str, feedback: dict) -> None:
        """Resume the workflow after HITL review."""
        config = {"configurable": {"thread_id": plan_id}}
        try:
            await self.graph.ainvoke(
                Command(resume=feedback), config
            )
        except Exception as exc:
            logger.exception("Workflow resume failed for plan %s", plan_id)
            await self.repo.update(plan_id, status="failed", error=str(exc))

    async def get_workflow_state(self, plan_id: str) -> Optional[dict]:
        """Read the latest snapshot from the checkpointer."""
        config = {"configurable": {"thread_id": plan_id}}
        try:
            snapshot = await self.graph.aget_state(config)
            return snapshot.values if snapshot else None
        except Exception:
            return None
