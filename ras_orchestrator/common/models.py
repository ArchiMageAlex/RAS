from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Tuple, Literal
from datetime import datetime


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


# ========== Phase 3: Self-Optimizing Models ==========

class SystemMetrics(BaseModel):
    """Метрики системы для RL и гомеостатического контроля."""
    cpu_load: float = Field(..., ge=0.0, le=1.0)
    latency_ms: float = Field(..., ge=0.0)
    error_rate: float = Field(..., ge=0.0, le=1.0)
    queue_depth: int = Field(..., ge=0)
    memory_usage: float = Field(..., ge=0.0, le=1.0)
    throughput: float = Field(..., ge=0.0)


class RLState(BaseModel):
    """Состояние для Reinforcement Learning."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    salience_scores: List[float] = Field(default_factory=list)
    current_mode: SystemMode
    interrupt_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    system_metrics: SystemMetrics


class RLAction(BaseModel):
    """Действие RL агента."""
    action_type: Literal["adjust_salience_weights", "adjust_mode_thresholds", "adjust_interrupt_thresholds"]
    parameters: Dict[str, Any]


class ForecastPoint(BaseModel):
    """Точка прогноза."""
    timestamp: datetime
    predicted_value: float
    lower_bound: float
    upper_bound: float


class Forecast(BaseModel):
    """Прогноз временного ряда."""
    event_type: str
    horizon_hours: int
    confidence_level: float
    predictions: List[ForecastPoint]
    recommended_actions: List[Dict[str, Any]] = Field(default_factory=list)


class Pattern(BaseModel):
    """Обнаруженный паттерн во временном ряду."""
    pattern_type: Literal["seasonality", "trend", "anomaly", "correlation"]
    parameters: Dict[str, Any]
    confidence: float
    start_time: datetime
    end_time: datetime


class ControlAction(BaseModel):
    """Корректирующее действие гомеостатического контроллера."""
    component: Literal["task_orchestrator", "interrupt_manager", "mode_manager", "retriever_agent"]
    action_type: str
    parameters: Dict[str, Any]


class HomeostaticState(BaseModel):
    """Состояние гомеостаза системы."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metrics: Dict[str, float]
    target_ranges: Dict[str, Tuple[float, float]]
    current_actions: List[ControlAction] = Field(default_factory=list)
    deviation_score: float = 0.0