import logging
import uuid
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

from common.models import Event, EventType, Severity
from common.telemetry import init_observability, get_tracer, business_metrics, system_metrics, instrument_fastapi
from common.utils import EVENT_COUNTER
from event_bus.kafka_client import produce_event
from policy_engine.api import router as policy_router
from human_escalation.escalation_manager import EscalationManager

# Initialize observability
init_observability()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAS Orchestrator API Gateway", version="0.1.0")

# Instrument FastAPI with OpenTelemetry
instrument_fastapi(app)

# Подключаем роутер политик
app.include_router(policy_router)

# Tracer
tracer = get_tracer("api_gateway")

# Escalation manager
escalation_manager = EscalationManager()


# Import trace for status codes (lazy import for optional OpenTelemetry)
def _get_trace():
    try:
        from opentelemetry import trace as _trace
        return _trace
    except ImportError:
        return None


class EventRequest(BaseModel):
    type: EventType
    severity: Severity
    source: str
    payload: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}


class HumanResponseRequest(BaseModel):
    instance_id: str
    operator: str
    decision: str  # approve, reject, escalate, etc.
    notes: Optional[str] = None
    metadata: Dict[str, Any] = {}


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Middleware для добавления correlation ID в заголовки."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    # Вставить correlation ID в baggage OpenTelemetry (если доступен)
    try:
        from opentelemetry import baggage
        ctx = baggage.set_baggage("correlation_id", correlation_id)
    except ImportError:
        pass
    # Пропустить запрос
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.post("/events", response_model=Dict[str, Any])
async def ingest_event(event_req: EventRequest, request: Request):
    """Приём события и отправка в event bus."""
    # Safe tracer context manager
    from contextlib import nullcontext
    span = None
    context_manager = tracer.start_as_current_span("ingest_event") if tracer else nullcontext()
    
    with context_manager as active_span:
        span = active_span
        if span:
            span.set_attribute("event.type", event_req.type.value)
            span.set_attribute("event.severity", event_req.severity.value)
            span.set_attribute("event.source", event_req.source)

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
            # Increment event counter
            EVENT_COUNTER.labels(event_type=event.type.value, severity=event.severity.value).inc()
            # Record metric
            if business_metrics and "interrupt_rate" in business_metrics:
                business_metrics["interrupt_rate"].add(1, {"type": "event_ingested"})
            return {
                "event_id": event_id,
                "status": "accepted",
                "message": "Event is being processed.",
            }
        except Exception as e:
            logger.error(f"Failed to produce event: {e}")
            if span:
                span.record_exception(e)
                trace_module = _get_trace()
                if trace_module:
                    span.set_status(trace_module.Status(trace_module.StatusCode.ERROR, str(e)))
            if system_metrics and "service_error_rate" in system_metrics:
                system_metrics["service_error_rate"].add(1)
            raise HTTPException(status_code=500, detail="Event ingestion failed.")


@app.post("/escalation/response", response_model=Dict[str, Any])
async def handle_human_response(response_req: HumanResponseRequest, request: Request):
    """Обрабатывает ответ оператора на эскалацию."""
    from contextlib import nullcontext
    span = None
    context_manager = tracer.start_as_current_span("handle_human_response") if tracer else nullcontext()
    
    with context_manager as active_span:
        span = active_span
        if span:
            span.set_attribute("escalation.instance_id", response_req.instance_id)
            span.set_attribute("escalation.operator", response_req.operator)
            span.set_attribute("escalation.decision", response_req.decision)

        try:
            instance = escalation_manager.handle_human_response(
                instance_id=response_req.instance_id,
                operator=response_req.operator,
                decision=response_req.decision,
                notes=response_req.notes,
                metadata=response_req.metadata
            )
            if instance is None:
                logger.warning(f"Escalation instance {response_req.instance_id} not found")
                raise HTTPException(status_code=404, detail="Escalation instance not found")
            logger.info(f"Human response processed for instance {response_req.instance_id}")
            return {
                "instance_id": instance.instance_id,
                "status": instance.status,
                "message": "Human response accepted",
            }
        except Exception as e:
            logger.error(f"Failed to process human response: {e}")
            if span:
                span.record_exception(e)
                trace_module = _get_trace()
                if trace_module:
                    span.set_status(trace_module.Status(trace_module.StatusCode.ERROR, str(e)))
            if system_metrics and "service_error_rate" in system_metrics:
                system_metrics["service_error_rate"].add(1)
            raise HTTPException(status_code=500, detail="Failed to process human response.")


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/metrics")
async def metrics():
    """Endpoint для Prometheus метрик (если используется prometheus-client)."""
    from prometheus_client import generate_latest
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(generate_latest())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)