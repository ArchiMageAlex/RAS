from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Tuple
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


class HistoricalEvent(Event):
    """
    Историческое событие, хранимое в репозитории для анализа новизны.
    Наследует все поля Event и добавляет оценку новизны.
    """
    novelty_score: float = Field(0.0, ge=0.0, le=1.0, description="Оценка новизны события (0-1)")


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
    """Метрики системы для RL и гомеостаза."""
    cpu_load: float = Field(..., ge=0.0, le=1.0, description="Загрузка CPU (0-1)")
    latency_ms: float = Field(..., ge=0.0, description="Задержка в миллисекундах")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Частота ошибок (0-1)")
    queue_depth: int = Field(..., ge=0, description="Глубина очереди задач")
    memory_usage: float = Field(0.0, ge=0.0, le=1.0, description="Использование памяти (0-1)")
    throughput: float = Field(0.0, ge=0.0, description="Пропускная способность (запросов/сек)")


class RLState(BaseModel):
    """Состояние среды RL."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    salience_scores: List[float] = Field(..., description="Список оценок значимости")
    current_mode: SystemMode
    interrupt_decisions: List[Dict[str, Any]] = Field(default_factory=list, description="Решения о прерываниях")
    system_metrics: SystemMetrics


class RLAction(BaseModel):
    """Действие RL агента."""
    action_type: str = Field(..., description="Тип действия (adjust_salience_weights, adjust_mode_thresholds, ...)")
    parameters: Dict[str, float] = Field(default_factory=dict, description="Параметры действия")


class ControlAction(BaseModel):
    """Корректирующее действие гомеостатического контроллера."""
    component: str = Field(..., description="Целевой компонент (task_orchestrator, load_balancer, ...)")
    action_type: str = Field(..., description="Тип действия (scale_agents, throttle, adjust_mode, ...)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Параметры действия")


class HomeostaticState(BaseModel):
    """Состояние гомеостатического контроллера."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metrics: Dict[str, float] = Field(..., description="Текущие метрики системы")
    target_ranges: Dict[str, Tuple[float, float]] = Field(..., description="Целевые диапазоны для каждой метрики")
    current_actions: List[ControlAction] = Field(default_factory=list, description="Активные корректирующие действия")
    deviation_score: float = Field(..., description="Общая оценка отклонения")


class ForecastPoint(BaseModel):
    """Точка прогноза временного ряда."""
    timestamp: datetime = Field(..., description="Временная метка прогноза")
    predicted_value: float = Field(..., ge=0.0, le=1.0, description="Предсказанное значение (0-1)")
    lower_bound: float = Field(..., ge=0.0, le=1.0, description="Нижняя граница доверительного интервала")
    upper_bound: float = Field(..., ge=0.0, le=1.0, description="Верхняя граница доверительного интервала")


class Forecast(BaseModel):
    """Прогноз временного ряда для типа событий."""
    event_type: str = Field(..., description="Тип событий (например, SECURITY_ALERT)")
    horizon_hours: int = Field(..., ge=1, description="Горизонт прогноза в часах")
    confidence_level: float = Field(..., ge=0.0, le=1.0, description="Уровень доверия прогноза (0-1)")
    predictions: List[ForecastPoint] = Field(..., description="Список точек прогноза")
    recommended_actions: List[Dict[str, Any]] = Field(default_factory=list, description="Рекомендованные действия")


class Pattern(BaseModel):
    """Паттерн, обнаруженный во временном ряду."""
    pattern_type: str = Field(..., description="Тип паттерна (seasonality, trend, anomaly, correlation)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Параметры паттерна")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность в обнаружении (0-1)")
    start_time: datetime = Field(..., description="Начало временного интервала паттерна")
    end_time: datetime = Field(..., description="Конец временного интервала паттерна")


class SourceTrust(BaseModel):
    """Модель доверия к источнику событий."""
    source: str = Field(..., description="Идентификатор источника")
    trust_score: float = Field(0.5, ge=0.0, le=1.0, description="Общая оценка доверия (0-1)")
    events_count: int = Field(0, ge=0, description="Количество событий от этого источника")
    accuracy: float = Field(1.0, ge=0.0, le=1.0, description="Точность предсказаний источника (0-1)")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Время последнего обновления")
    reliability_metrics: Dict[str, float] = Field(default_factory=dict, description="Дополнительные метрики надёжности")


class TaskCheckpoint(BaseModel):
    """Чекпоинт задачи для возможности возобновления."""
    checkpoint_id: str = Field(..., description="Уникальный идентификатор чекпоинта")
    task_id: str = Field(..., description="Идентификатор задачи")
    agent_type: str = Field(..., description="Тип агента, выполняющего задачу")
    state_data: str = Field(..., description="Сериализованное состояние агента")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Время создания чекпоинта")
    expires_at: Optional[datetime] = Field(None, description="Время истечения срока действия (опционально)")