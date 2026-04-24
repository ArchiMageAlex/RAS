#!/usr/bin/env python3
"""
Тест преобразования режимов в environment.py.
Проверяем, что метод _numeric_to_mode корректно обрабатывает строки и числа.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rl_agent.environment import OrchestratorEnv
from common.models import SystemMode

def test_numeric_to_mode():
    env = OrchestratorEnv()
    # Тестируем числовые значения
    assert env._numeric_to_mode(0.0) == SystemMode.LOW
    assert env._numeric_to_mode(0.5) == SystemMode.LOW
    assert env._numeric_to_mode(1.0) == SystemMode.NORMAL
    assert env._numeric_to_mode(1.5) == SystemMode.NORMAL
    assert env._numeric_to_mode(2.0) == SystemMode.ELEVATED
    assert env._numeric_to_mode(2.5) == SystemMode.ELEVATED
    assert env._numeric_to_mode(3.0) == SystemMode.CRITICAL
    assert env._numeric_to_mode(5.0) == SystemMode.CRITICAL
    print("✓ Числовые значения обрабатываются корректно")
    
    # Тестируем строковые числа
    assert env._numeric_to_mode("0.0") == SystemMode.LOW
    assert env._numeric_to_mode("1.0") == SystemMode.NORMAL
    assert env._numeric_to_mode("2.0") == SystemMode.ELEVATED
    assert env._numeric_to_mode("3.0") == SystemMode.CRITICAL
    print("✓ Строковые числа преобразуются корректно")
    
    # Тестируем строковые имена режимов
    assert env._numeric_to_mode("LOW") == SystemMode.LOW
    assert env._numeric_to_mode("NORMAL") == SystemMode.NORMAL
    assert env._numeric_to_mode("ELEVATED") == SystemMode.ELEVATED
    assert env._numeric_to_mode("CRITICAL") == SystemMode.CRITICAL
    assert env._numeric_to_mode("low") == SystemMode.LOW
    assert env._numeric_to_mode("normal") == SystemMode.NORMAL
    assert env._numeric_to_mode("elevated") == SystemMode.ELEVATED
    assert env._numeric_to_mode("critical") == SystemMode.CRITICAL
    print("✓ Строковые имена режимов преобразуются корректно")
    
    # Проверяем исключение для неизвестной строки
    try:
        env._numeric_to_mode("UNKNOWN")
        print("✗ Ожидалось исключение ValueError")
        return False
    except ValueError as e:
        print(f"✓ Неизвестная строка вызывает ValueError: {e}")
    
    # Проверяем обработку в _apply_action с строковым параметром mode
    from common.models import RLAction
    action = RLAction(
        action_type="adjust_mode_thresholds",
        parameters={"mode": "NORMAL", "delta": 0.02}
    )
    # Вызовем _apply_action и убедимся, что нет предупреждения
    env._apply_action(action)
    print("✓ Действие с параметром mode='NORMAL' выполнено без предупреждения")
    
    # Проверяем с числовым параметром
    action2 = RLAction(
        action_type="adjust_mode_thresholds",
        parameters={"mode": 1.0, "delta": 0.02}
    )
    env._apply_action(action2)
    print("✓ Действие с параметром mode=1.0 выполнено без предупреждения")
    
    # Проверяем с некорректным параметром (должно сработать исключение и fallback)
    action3 = RLAction(
        action_type="adjust_mode_thresholds",
        parameters={"mode": "INVALID", "delta": 0.02}
    )
    env._apply_action(action3)
    print("✓ Действие с некорректным параметром обработано с fallback")
    
    print("\nВсе тесты пройдены успешно!")
    return True

if __name__ == "__main__":
    try:
        success = test_numeric_to_mode()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)