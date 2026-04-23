"""
Homeostatic Controller для фазы 3 (Self-Optimizing).
Поддержание гомеостаза системы через балансировку нагрузки, приоритизацию и масштабирование.
"""

from .controller import HomeostaticController
from .metrics_collector import MetricsCollector
from .load_balancer import LoadBalancer
from .priority_manager import PriorityManager
from .resource_allocator import ResourceAllocator

__version__ = "0.1.0"
__all__ = [
    "HomeostaticController",
    "MetricsCollector",
    "LoadBalancer",
    "PriorityManager",
    "ResourceAllocator",
]