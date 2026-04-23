#!/usr/bin/env python3
"""
Проверка импорта модулей фазы 3 Self-Optimizing.
"""
import sys
import traceback

MODULES = [
    ("predictive_engine", "PredictiveEngine"),
    ("predictive_engine.timeseries_store", "TimeseriesStore"),
    ("predictive_engine.pattern_detector", "PatternDetector"),
    ("predictive_engine.forecast_models", "BaseForecastModel"),
    ("predictive_engine.proactive_actions", "ProactiveActionGenerator"),
    ("homeostatic_controller", "HomeostaticController"),
    ("homeostatic_controller.metrics_collector", "MetricsCollector"),
    ("homeostatic_controller.load_balancer", "LoadBalancer"),
    ("homeostatic_controller.priority_manager", "PriorityManager"),
    ("homeostatic_controller.resource_allocator", "ResourceAllocator"),
    ("rl_agent", "RLAgent"),
    ("rl_agent.environment", "OrchestratorEnv"),
    ("common.models", "RLState"),
    ("common.models", "SystemMetrics"),
    ("common.models", "Forecast"),
    ("common.models", "Pattern"),
    ("common.models", "ControlAction"),
    ("common.models", "HomeostaticState"),
]

def check_imports():
    errors = []
    for module_name, class_name in MODULES:
        try:
            module = __import__(module_name, fromlist=[class_name])
            if class_name:
                getattr(module, class_name)
            print(f"✓ {module_name}.{class_name if class_name else ''}")
        except ImportError as e:
            errors.append((module_name, class_name, f"ImportError: {e}"))
            print(f"✗ {module_name}.{class_name if class_name else ''} - ImportError: {e}")
        except AttributeError as e:
            errors.append((module_name, class_name, f"AttributeError: {e}"))
            print(f"✗ {module_name}.{class_name if class_name else ''} - AttributeError: {e}")
        except Exception as e:
            errors.append((module_name, class_name, f"Unexpected: {e}"))
            print(f"✗ {module_name}.{class_name if class_name else ''} - {e}")
            traceback.print_exc()
    return errors

if __name__ == "__main__":
    print("Проверка импорта модулей фазы 3...")
    errors = check_imports()
    if errors:
        print(f"\nНайдено {len(errors)} ошибок импорта:")
        for mod, cls, err in errors:
            print(f"  {mod}.{cls}: {err}")
        sys.exit(1)
    else:
        print("\nВсе модули успешно импортируются.")
        sys.exit(0)