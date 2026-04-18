# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from ai_travel_planner.apis.default_api_base import BaseDefaultApi
import ai_travel_planner.impl

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)

from ai_travel_planner.models.extra_models import TokenModel  # noqa: F401
from uuid import UUID
from ai_travel_planner.models.create_plan_request import CreatePlanRequest
from ai_travel_planner.models.create_plan_response import CreatePlanResponse
from ai_travel_planner.models.final_plan_response import FinalPlanResponse
from ai_travel_planner.models.plan_response import PlanResponse
from ai_travel_planner.models.review_request import ReviewRequest


router = APIRouter()

ns_pkg = ai_travel_planner.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/plan",
    responses={
        202: {"model": CreatePlanResponse, "description": "Accepted"},
    },
    tags=["default"],
    summary="Submit a new travel request",
    response_model_by_alias=True,
)
async def create_plan(
    create_plan_request: CreatePlanRequest = Body(None, description=""),
) -> CreatePlanResponse:
    if not BaseDefaultApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseDefaultApi.subclasses[0]().create_plan(create_plan_request)


@router.get(
    "/plan/{id}",
    responses={
        200: {"model": PlanResponse, "description": "OK"},
    },
    tags=["default"],
    summary="Get plan status and draft",
    response_model_by_alias=True,
)
async def get_plan(
    id: UUID = Path(..., description=""),
) -> PlanResponse:
    if not BaseDefaultApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseDefaultApi.subclasses[0]().get_plan(id)


@router.post(
    "/plan/{id}/review",
    responses={
        200: {"model": PlanResponse, "description": "Updated plan"},
    },
    tags=["default"],
    summary="Submit HITL feedback",
    response_model_by_alias=True,
)
async def review_plan(
    id: UUID = Path(..., description=""),
    review_request: ReviewRequest = Body(None, description=""),
) -> PlanResponse:
    if not BaseDefaultApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseDefaultApi.subclasses[0]().review_plan(id, review_request)


@router.get(
    "/plan/{id}/final",
    responses={
        200: {"model": FinalPlanResponse, "description": "Final itinerary"},
    },
    tags=["default"],
    summary="Get finalized plan",
    response_model_by_alias=True,
)
async def get_final_plan(
    id: UUID = Path(..., description=""),
) -> FinalPlanResponse:
    if not BaseDefaultApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseDefaultApi.subclasses[0]().get_final_plan(id)
