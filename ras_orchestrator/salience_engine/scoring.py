"""
Вспомогательные функции для оценки значимости.
"""


def normalize(value: float, min_val: float, max_val: float) -> float:
    """Нормализует значение в диапазон [0, 1]."""
    if max_val == min_val:
        return 0.5
    return (value - min_val) / (max_val - min_val)


def weighted_average(scores: dict, weights: dict) -> float:
    """Взвешенное среднее."""
    total = 0.0
    weight_sum = 0.0
    for key, score in scores.items():
        weight = weights.get(key, 0.0)
        total += score * weight
        weight_sum += weight
    return total / weight_sum if weight_sum > 0 else 0.0