import logging
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime

from common.models import Event, EventType, Severity
from event_bus.kafka_client import produce_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAS Orchestrator API Gateway", version="0.1.0")


class EventRequest(BaseModel):
    type: EventType
    severity: Severity
    source: str
    payload: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}


@app.post("/events", response_model=Dict[str, Any])
async def ingest_event(event_req: EventRequest):
    """Приём события и отправка в event bus."""
    event_id = str(uuid.uuid4())
    event = Event(
        event_id=event_id,
        type=event_req.type,
        severity=event_req.severity,
        source=event_req.source,
        timestamp=datetime.utcnow(),
        payload=event_req.payload,
        metadata=event_req.metadata,
    )

    try:
        # Отправка в Kafka
        await produce_event(event)
        logger.info(f"Event {event_id} ingested and sent to event bus.")
        return {
            "event_id": event_id,
            "status": "accepted",
            "message": "Event is being processed.",
        }
    except Exception as e:
        logger.error(f"Failed to produce event: {e}")
        raise HTTPException(status_code=500, detail="Event ingestion failed.")


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)