# coding: utf-8

from fastapi.testclient import TestClient


from uuid import UUID  # noqa: F401
from ai_travel_planner.models.create_plan_request import CreatePlanRequest  # noqa: F401
from ai_travel_planner.models.create_plan_response import CreatePlanResponse  # noqa: F401
from ai_travel_planner.models.final_plan_response import FinalPlanResponse  # noqa: F401
from ai_travel_planner.models.plan_response import PlanResponse  # noqa: F401
from ai_travel_planner.models.review_request import ReviewRequest  # noqa: F401


def test_create_plan(client: TestClient):
    """Test case for create_plan

    Submit a new travel request
    """
    create_plan_request = {"end_date":"2000-01-23","destination":"destination","interests":["interests","interests"],"travelers":1,"start_date":"2000-01-23","budget":{"min":0.8008281904610115,"max":6.027456183070403,"currency":"currency"}}

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/plan",
    #    headers=headers,
    #    json=create_plan_request,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_get_plan(client: TestClient):
    """Test case for get_plan

    Get plan status and draft
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/plan/{id}".format(id=UUID('38400000-8cf0-11bd-b23e-10b96e4ef00d')),
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_review_plan(client: TestClient):
    """Test case for review_plan

    Submit HITL feedback
    """
    review_request = {"comments":"comments","action":"approve","modifications":{"key":""}}

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/plan/{id}/review".format(id=UUID('38400000-8cf0-11bd-b23e-10b96e4ef00d')),
    #    headers=headers,
    #    json=review_request,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200


def test_get_final_plan(client: TestClient):
    """Test case for get_final_plan

    Get finalized plan
    """

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "GET",
    #    "/plan/{id}/final".format(id=UUID('38400000-8cf0-11bd-b23e-10b96e4ef00d')),
    #    headers=headers,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

