"""
Models for human escalation workflows.
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime


class EscalationAction(str, Enum):
    """Действия в рамках эскалации."""
    NOTIFY = "notify"
    WAIT_FOR_RESPONSE = "wait_for_response"
    EXECUTE_SCRIPT = "execute_script"
    CREATE_TASK = "create_task"
    LOG = "log"


class EscalationStep(BaseModel):
    """Шаг workflow эскалации."""
    action: EscalationAction
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Optional[int] = None
    retry_count: int = 0


class EscalationWorkflow(BaseModel):
    """Workflow эскалации к человеку-оператору."""
    workflow_id: str
    trigger_policy: str
    steps: List[EscalationStep]
    timeout_seconds: int = 3600  # общий таймаут workflow
    notify_channels: List[str] = Field(default_factory=list)  # slack, email, pagerduty
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending, running, completed, failed, waiting_for_response


class EscalationInstance(BaseModel):
    """Экземпляр запущенного workflow."""
    instance_id: str
    workflow_id: str
    event_id: str
    status: str
    current_step: int = 0
    step_results: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    timeout_at: Optional[datetime] = None
    human_response: Optional[Dict[str, Any]] = None


class HumanResponse(BaseModel):
    """Ответ оператора на эскалацию."""
    response_id: str
    instance_id: str
    operator: str
    decision: str  # approve, reject, escalate, custom
    notes: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)