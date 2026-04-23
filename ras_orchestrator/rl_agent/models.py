"""
Pydantic модели для RL агента (дополнение к common.models).
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class Episode(BaseModel):
    """Эпизод обучения RL."""
    model_config = ConfigDict(protected_namespaces=())
    episode_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    total_reward: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TrainingConfig(BaseModel):
    """Конфигурация обучения RL."""
    model_config = ConfigDict(protected_namespaces=())
    algorithm: str = "DQN"
    learning_rate: float = 0.001
    gamma: float = 0.99
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 0.995
    batch_size: int = 64
    memory_size: int = 10000
    target_update_frequency: int = 100
    max_episode_length: int = 1000


class ModelCheckpoint(BaseModel):
    """Чекпоинт модели RL."""
    model_config = ConfigDict(protected_namespaces=())
    checkpoint_id: str
    timestamp: datetime
    model_path: str
    metrics: Dict[str, float]
    config: TrainingConfig