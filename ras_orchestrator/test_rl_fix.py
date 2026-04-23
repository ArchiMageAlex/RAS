#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправлений в RL агенте.
"""
import sys
sys.path.insert(0, '.')

from ras_orchestrator.rl_agent.environment import OrchestratorEnv
from ras_orchestrator.common.models import RLAction, RLState, SystemMetrics, SystemMode
from datetime import datetime

def test_environment():
    print("1. Создание окружения...")
    env = OrchestratorEnv()
    state = env.reset()
    print(f"   Состояние создано, режим: {state.current_mode}")
    
    # Проверка метода _mode_to_numeric
    numeric = env._mode_to_numeric(state.current_mode)
    print(f"   Числовое представление режима: {numeric}")
    
    # Проверка get_state_vector
    vec = env.get_state_vector(state)
    print(f"   Вектор состояния shape: {vec.shape}")
    
    # Создание действия с параметрами (смешанные типы)
    action = RLAction(
        action_type="adjust_mode_thresholds",
        parameters={"mode": "NORMAL", "delta": 0.02}
    )
    print(f"2. Действие создано: {action}")
    print(f"   Параметры: {action.parameters}, тип параметров: {type(action.parameters)}")
    
    # Выполнение шага
    print("3. Выполнение шага в среде...")
    next_state, reward, done, info = env.step(action)
    print(f"   Новое состояние: режим {next_state.current_mode}")
    print(f"   Награда: {reward}, завершено: {done}")
    
    # Проверка, что параметры правильно извлекаются в environment
    print("4. Проверка извлечения параметров в environment...")
    # Внутри environment._apply_action используется action.parameters.get("mode") и action.parameters.get("delta")
    # Если нет ошибок, значит всё работает.
    
    print("5. Проверка функции _default_parameters в agent...")
    from ras_orchestrator.rl_agent.agent import RLAgent
    agent = RLAgent(env)
    params = agent._default_parameters("adjust_mode_thresholds")
    print(f"   Параметры по умолчанию: {params}")
    print(f"   Тип params: {type(params)}")
    # Создание RLAction с этими параметрами
    test_action = RLAction(action_type="adjust_mode_thresholds", parameters=params)
    print(f"   Созданное действие: {test_action}")
    
    print("\nВсе проверки пройдены успешно.")
    return True

if __name__ == "__main__":
    try:
        test_environment()
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)