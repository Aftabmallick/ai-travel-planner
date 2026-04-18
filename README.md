# AI Travel Planner API

This is an AI-powered multi-agent travel planning assistant with Human-in-the-Loop (HITL) approval, served via FastAPI.

## Requirements

Python 3.12+

## Installation & Usage

To run the server, execute the following from the root directory:

```bash
uv venv venv
venv\Scripts\activate
uv pip install -r requirements.txt
cd src/
copy .env.example .env   # copy paste your api keys here
python -m ai_travel_planner.main
```

Open your browser at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to see the interactive Swagger UI documentation.

## API Endpoints Usage

The system uses an asynchronous workflow. Here is the typical flow of interacting with the API:

### 1. Create a Travel Plan (`POST /plan`)

Submit a travel request. This starts the background AI workflow and returns a `plan_id`.

```bash
curl -X POST "http://127.0.0.1:8000/plan" \
     -H "Content-Type: application/json" \
     -d '{
       "destination": "Paris, France",
       "start_date": "2026-06-01",
       "end_date": "2026-06-05",
       "travelers": 2,
       "interests": ["history", "food", "art"],
       "budget": {
         "min": 2000,
         "max": 5000,
         "currency": "USD"
       }
     }'
```
**Response:**
```json
{
  "plan_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending"
}
```

### 2. Check Plan Status (`GET /plan/{id}`)

Poll this endpoint to check the progress of the workflow. The workflow moves through stages (`intake` -> `research` -> `itinerary_generation`). Once it reaches `awaiting_review`, you can inspect the `draft_itinerary`.

```bash
curl "http://127.0.0.1:8000/plan/123e4567-e89b-12d3-a456-426614174000"
```

### 3. Review the Plan (`POST /plan/{id}/review`)

Once the plan is in the `awaiting_review` status, submit Human-in-the-Loop (HITL) feedback. You can `approve`, `reject`, or `modify` the itinerary.

**To Approve:**
```bash
curl -X POST "http://127.0.0.1:8000/plan/123e4567-e89b-12d3-a456-426614174000/review" \
     -H "Content-Type: application/json" \
     -d '{
       "action": "approve"
     }'
```

**To Request Modifications:**
```bash
curl -X POST "http://127.0.0.1:8000/plan/123e4567-e89b-12d3-a456-426614174000/review" \
     -H "Content-Type: application/json" \
     -d '{
       "action": "modify",
       "comments": "Can we swap out the museum visit for a food tour on Day 2?"
     }'
```
*Note: Requesting modifications will move the status to `revising` and kick off the AI agents again. You'll need to poll `GET /plan/{id}` until it is `awaiting_review` again.*

### 4. Get the Final Plan (`GET /plan/{id}/final`)

Once the plan has been `approved`, fetch the final, locked itinerary here.

```bash
curl "http://127.0.0.1:8000/plan/123e4567-e89b-12d3-a456-426614174000/final"
```
