from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
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


class SystemMetrics(BaseModel):
    """Метрики системы для RL-агента."""
    cpu_load: float = Field(..., ge=0.0, le=1.0, description="Загрузка CPU (0-1)")
    latency_ms: float = Field(..., ge=0.0, description="Задержка в миллисекундах")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Частота ошибок (0-1)")
    queue_depth: int = Field(..., ge=0, description="Глубина очереди задач")
    memory_usage: float = Field(..., ge=0.0, le=1.0, description="Использование памяти (0-1)")
    throughput: float = Field(..., ge=0.0, description="Пропускная способность (запросов/сек)")


class RLState(BaseModel):
    """Состояние системы для RL-агента."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    salience_scores: List[float] = Field(..., description="Список оценок значимости")
    current_mode: SystemMode = Field(..., description="Текущий режим системы")
    interrupt_decisions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="История решений о прерываниях"
    )
    system_metrics: SystemMetrics = Field(..., description="Метрики системы")


class RLAction(BaseModel):
    """Действие RL-агента."""
    action_type: str = Field(..., description="Тип действия (adjust_salience_weights и т.д.)")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Параметры действия (delta, mode и др.)"
    )