"""
API implementation – wires the generated OpenAPI base class to the
service layer.

By subclassing ``BaseDefaultApi`` this module is auto-discovered by
the ``pkgutil.iter_modules`` loop in ``default_api.py``.
"""

import logging
from uuid import UUID

from fastapi import HTTPException

from ai_travel_planner.apis.default_api_base import BaseDefaultApi
from ai_travel_planner.models.create_plan_request import CreatePlanRequest
from ai_travel_planner.models.create_plan_response import CreatePlanResponse
from ai_travel_planner.models.final_plan_response import FinalPlanResponse
from ai_travel_planner.models.itinerary import Itinerary
from ai_travel_planner.models.plan_response import PlanResponse
from ai_travel_planner.models.review_request import ReviewRequest

from ai_travel_planner.repository.plan_repository import PlanRepository
from ai_travel_planner.services.plan_service import PlanService
from ai_travel_planner.services.workflow import WorkflowService

logger = logging.getLogger(__name__)

# ── singleton wiring ─────────────────────────────────────
_repo = PlanRepository()
_workflow = WorkflowService(_repo)
_plan_service = PlanService(_repo, _workflow)


class DefaultApiImpl(BaseDefaultApi):
    """Concrete implementation of the travel-planner API."""

    # ── POST /plan ───────────────────────────────────────
    async def create_plan(
        self,
        create_plan_request: CreatePlanRequest,
    ) -> CreatePlanResponse:
        request_data = create_plan_request.to_dict()
        result = await _plan_service.create_plan(request_data)

        return CreatePlanResponse(
            plan_id=result["plan_id"],
            status=result["status"],
        )

    # ── GET /plan/{id} ───────────────────────────────────
    async def get_plan(self, id: UUID) -> PlanResponse:
        plan = await _plan_service.get_plan(str(id))
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan not found")

        draft = None
        if plan.get("draft_itinerary"):
            draft = _build_itinerary(plan["draft_itinerary"])

        return PlanResponse(
            plan_id=plan["plan_id"],
            status=plan["status"],
            stage=plan.get("stage"),
            draft_itinerary=draft,
        )

    # ── POST /plan/{id}/review ───────────────────────────
    async def review_plan(
        self,
        id: UUID,
        review_request: ReviewRequest,
    ) -> PlanResponse:
        feedback = review_request.to_dict()
        result = await _plan_service.submit_review(str(id), feedback)

        if result is None:
            raise HTTPException(status_code=404, detail="Plan not found")

        if "error" in result and result.get("status") != "approved":
            raise HTTPException(status_code=409, detail=result["error"])

        draft = None
        if result.get("draft_itinerary"):
            draft = _build_itinerary(result["draft_itinerary"])

        return PlanResponse(
            plan_id=result.get("plan_id", str(id)),
            status=result.get("status", "revising"),
            stage=result.get("stage"),
            draft_itinerary=draft,
        )

    # ── GET /plan/{id}/final ─────────────────────────────
    async def get_final_plan(self, id: UUID) -> FinalPlanResponse:
        result = await _plan_service.get_final_plan(str(id))

        if result is None:
            raise HTTPException(status_code=404, detail="Plan not found")

        if "error" in result:
            raise HTTPException(status_code=409, detail=result["error"])

        final_itin = None
        if result.get("final_itinerary"):
            final_itin = _build_itinerary(result["final_itinerary"])

        return FinalPlanResponse(
            plan_id=result["plan_id"],
            status="approved",
            final_itinerary=final_itin,
        )


# ── helpers ──────────────────────────────────────────────
def _build_itinerary(data: dict) -> Itinerary:
    """Convert a raw dict into an Itinerary model, tolerating missing keys."""
    if not data or not isinstance(data, dict):
        return None
    try:
        return Itinerary.from_dict(data)
    except Exception:
        logger.warning("Could not parse itinerary dict, returning raw")
        return Itinerary(destination=data.get("destination", ""), days=[])
