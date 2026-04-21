from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta


class EventType(str, Enum):
    PAYMENT_OUTAGE = "payment_outage"
    SECURITY_ALERT = "security_alert"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    USER_COMPLAINT = "user_complaint"
    SYSTEM_HEALTH = "system_health"
    CUSTOM = "custom"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Event(BaseModel):
    event_id: str = Field(..., description="Unique identifier for the event")
    type: EventType
    severity: Severity
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SalienceScore(BaseModel):
    relevance: float = Field(..., ge=0.0, le=1.0)
    novelty: float = Field(..., ge=0.0, le=1.0)
    risk: float = Field(..., ge=0.0, le=1.0)
    urgency: float = Field(..., ge=0.0, le=1.0)
    uncertainty: float = Field(..., ge=0.0, le=1.0)
    aggregated: float = Field(..., ge=0.0, le=1.0)


class SystemMode(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    ELEVATED = "elevated"
    CRITICAL = "critical"


class Task(BaseModel):
    task_id: str
    event_id: str
    agent_type: str
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None


# Phase 2: Novelty Detection
class HistoricalEvent(BaseModel):
    event_id: str
    type: EventType
    severity: Severity
    source: str
    timestamp: datetime
    payload: Dict[str, Any]
    novelty_score: Optional[float] = None


# Phase 2: Checkpoint/Resume
class TaskCheckpoint(BaseModel):
    checkpoint_id: str
    task_id: str
    agent_type: str
    state_data: bytes  # pickle-сериализованное состояние
    created_at: datetime
    expires_at: Optional[datetime]


# Phase 2: Trust Scoring
class SourceTrust(BaseModel):
    source: str
    trust_score: float = 0.5  # 0.0 – недоверенный, 1.0 – доверенный
    events_count: int = 0
    accuracy: float = 1.0     # Точность предыдущих предсказаний
    last_updated: datetime


# Phase 2: Human Escalation
class EscalationStep(BaseModel):
    action: str  # notify, wait_for_response, execute_script
    parameters: Dict[str, Any]


class EscalationWorkflow(BaseModel):
    workflow_id: str
    trigger_policy: str
    steps: List[EscalationStep]
    timeout_seconds: int
    notify_channels: List[str]  # slack, email, pagerduty