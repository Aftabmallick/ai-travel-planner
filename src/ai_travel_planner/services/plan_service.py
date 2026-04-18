"""
Plan service – the bridge between the FastAPI API layer and the
LangGraph workflow.

Handles input conversion, background task dispatch, and response
assembly so the API impl stays thin.
"""

import asyncio
import logging
from typing import Any, Optional
from uuid import uuid4

from ai_travel_planner.repository.plan_repository import PlanRepository
from ai_travel_planner.services.workflow import WorkflowService

logger = logging.getLogger(__name__)


class PlanService:
    """High-level service consumed by the API implementation."""

    def __init__(self, repo: PlanRepository, workflow: WorkflowService) -> None:
        self.repo = repo
        self.workflow = workflow

    # ── POST /plan ───────────────────────────────────────
    async def create_plan(self, request_data: dict) -> dict:
        """Create a new plan and launch the workflow as a background task.

        Returns ``{"plan_id": ..., "status": "pending"}`` immediately.
        """
        plan_id = str(uuid4())
        await self.repo.create(plan_id, request_data)

        # Fire-and-forget background task
        asyncio.create_task(
            self._run_workflow_safe(plan_id, request_data),
            name=f"workflow-{plan_id}",
        )

        return {"plan_id": plan_id, "status": "pending"}

    async def _run_workflow_safe(self, plan_id: str, request_data: dict) -> None:
        """Wrapper that catches exceptions so the task never crashes silently."""
        try:
            await self.workflow.start_workflow(plan_id, request_data)
        except Exception as exc:
            logger.exception("Background workflow crashed for plan %s", plan_id)
            try:
                await self.repo.update(plan_id, status="failed", error=str(exc))
            except Exception:
                logger.exception("Failed to update repo after crash")

    # ── GET /plan/{id} ───────────────────────────────────
    async def get_plan(self, plan_id: str) -> Optional[dict]:
        """Return the current plan state, or None if not found."""
        record = await self.repo.get(plan_id)
        if record is None:
            return None
        return record.to_dict()

    # ── POST /plan/{id}/review ───────────────────────────
    async def submit_review(self, plan_id: str, feedback: dict) -> Optional[dict]:
        """Submit HITL feedback and resume the workflow.

        Returns the updated plan state, or None if plan not found.
        """
        record = await self.repo.get(plan_id)
        if record is None:
            return None

        if record.status != "awaiting_review":
            return {
                "error": f"Plan is in '{record.status}' state, not awaiting review",
                "plan_id": plan_id,
                "status": record.status,
            }

        # Mark as revising (for approve it will quickly become approved)
        action = feedback.get("action", "approve")
        if action == "approve":
            await self.repo.update(plan_id, status="approved")
        else:
            await self.repo.update(plan_id, status="revising", stage="revision")

        # Resume the workflow in the background
        asyncio.create_task(
            self._resume_workflow_safe(plan_id, feedback),
            name=f"resume-{plan_id}",
        )

        # Return current state immediately
        record = await self.repo.get(plan_id)
        return record.to_dict() if record else None

    async def _resume_workflow_safe(self, plan_id: str, feedback: dict) -> None:
        try:
            await self.workflow.resume_workflow(plan_id, feedback)
        except Exception as exc:
            logger.exception("Resume workflow crashed for plan %s", plan_id)
            try:
                await self.repo.update(plan_id, status="failed", error=str(exc))
            except Exception:
                logger.exception("Failed to update repo after resume crash")

    # ── GET /plan/{id}/final ─────────────────────────────
    async def get_final_plan(self, plan_id: str) -> Optional[dict]:
        """Return the finalized plan, or an error dict if not yet approved."""
        record = await self.repo.get(plan_id)
        if record is None:
            return None

        if record.status != "approved" or not record.final_itinerary:
            return {
                "error": "Plan is not yet finalized",
                "plan_id": plan_id,
                "status": record.status,
                "stage": record.stage,
            }

        return {
            "plan_id": plan_id,
            "status": "approved",
            "final_itinerary": record.final_itinerary,
        }
