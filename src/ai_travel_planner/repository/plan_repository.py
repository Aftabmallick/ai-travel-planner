"""
In-memory repository for travel-plan state persistence.

Uses an asyncio lock so concurrent FastAPI requests are safe.
The repository is the single source of truth that the API layer reads;
the LangGraph checkpointer handles internal workflow state separately.
"""

import asyncio
import copy
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PlanRecord:
    """Mutable record that tracks every facet of a travel plan."""

    def __init__(self, plan_id: str, request_data: dict):
        self.plan_id: str = plan_id
        self.request_data: dict = request_data

        # Workflow tracking
        self.status: str = "pending"           # mirrors PlanStatus enum
        self.stage: str = "intake"             # mirrors WorkflowStage enum

        # Agent outputs
        self.research_data: Optional[str] = None
        self.draft_itinerary: Optional[dict] = None
        self.final_itinerary: Optional[dict] = None

        # Error / revision info
        self.error: Optional[str] = None
        self.revision_count: int = 0

        # Timestamps
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.updated_at: str = datetime.now(timezone.utc).isoformat()

    # ── helpers ──────────────────────────────────────────
    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "request_data": self.request_data,
            "status": self.status,
            "stage": self.stage,
            "research_data": self.research_data,
            "draft_itinerary": copy.deepcopy(self.draft_itinerary),
            "final_itinerary": copy.deepcopy(self.final_itinerary),
            "error": self.error,
            "revision_count": self.revision_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class PlanRepository:
    """Thread-safe, in-memory store keyed by *plan_id* (str)."""

    def __init__(self) -> None:
        self._store: Dict[str, PlanRecord] = {}
        self._lock = asyncio.Lock()

    # ── CRUD ─────────────────────────────────────────────
    async def create(self, plan_id: str, request_data: dict) -> PlanRecord:
        async with self._lock:
            if plan_id in self._store:
                raise ValueError(f"Plan {plan_id} already exists")
            record = PlanRecord(plan_id, request_data)
            self._store[plan_id] = record
            logger.info("Created plan record %s", plan_id)
            return record

    async def get(self, plan_id: str) -> Optional[PlanRecord]:
        async with self._lock:
            return self._store.get(plan_id)

    async def update(self, plan_id: str, **fields: Any) -> PlanRecord:
        """Update arbitrary fields on the record and bump *updated_at*."""
        async with self._lock:
            record = self._store.get(plan_id)
            if record is None:
                raise KeyError(f"Plan {plan_id} not found")
            for key, value in fields.items():
                if not hasattr(record, key):
                    raise AttributeError(f"PlanRecord has no field '{key}'")
                setattr(record, key, value)
            record.touch()
            logger.debug("Updated plan %s: %s", plan_id, list(fields.keys()))
            return record

    async def exists(self, plan_id: str) -> bool:
        async with self._lock:
            return plan_id in self._store
