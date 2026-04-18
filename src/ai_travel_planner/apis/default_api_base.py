# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from uuid import UUID
from ai_travel_planner.models.create_plan_request import CreatePlanRequest
from ai_travel_planner.models.create_plan_response import CreatePlanResponse
from ai_travel_planner.models.final_plan_response import FinalPlanResponse
from ai_travel_planner.models.plan_response import PlanResponse
from ai_travel_planner.models.review_request import ReviewRequest


class BaseDefaultApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseDefaultApi.subclasses = BaseDefaultApi.subclasses + (cls,)
    async def create_plan(
        self,
        create_plan_request: CreatePlanRequest,
    ) -> CreatePlanResponse:
        ...


    async def get_plan(
        self,
        id: UUID,
    ) -> PlanResponse:
        ...


    async def review_plan(
        self,
        id: UUID,
        review_request: ReviewRequest,
    ) -> PlanResponse:
        ...


    async def get_final_plan(
        self,
        id: UUID,
    ) -> FinalPlanResponse:
        ...
