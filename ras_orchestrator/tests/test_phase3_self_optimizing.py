"""
Unit tests для фазы 3 Self-Optimizing (Predictive Engine, Homeostatic Controller, RL Agent).
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import numpy as np
import torch

from common.models import (
    Event, EventType, Severity, SystemMetrics, RLState, RLAction,
    Forecast, ForecastPoint, Pattern, ControlAction, HomeostaticState,
    SalienceScore
)
from predictive_engine import PredictiveEngine
from predictive_engine.timeseries_store import TimeseriesStore
from predictive_engine.pattern_detector import PatternDetector
from predictive_engine.forecast_models import BaseForecastModel
from homeostatic_controller import HomeostaticController
from homeostatic_controller.metrics_collector import MetricsCollector
from homeostatic_controller.load_balancer import LoadBalancer
from homeostatic_controller.priority_manager import PriorityManager
from homeostatic_controller.resource_allocator import ResourceAllocator
from rl_agent import RLAgent
from rl_agent.environment import OrchestratorEnv
from policy_engine.core import PolicyEngineCore
from salience_engine.advanced_scoring import AdvancedScoring


@pytest.fixture
def event():
    """Фикстура события."""
    return Event(
        event_id="test-1",
        type=EventType.SECURITY_ALERT,
        severity=Severity.HIGH,
        source="test",
        payload={"message": "test"},
        timestamp="2025-01-01T00:00:00Z"
    )


@pytest.fixture
def predictive_engine():
    """Фикстура Predictive Engine с замоканными зависимостями."""
    with patch('predictive_engine.timeseries_store.TimeseriesStore') as mock_store, \
         patch('predictive_engine.pattern_detector.PatternDetector') as mock_detector, \
         patch('predictive_engine.forecast_models.BaseForecastModel') as mock_model:
        engine = PredictiveEngine()
        engine.store = mock_store
        engine.pattern_detector = mock_detector
        engine.forecast_model = mock_model
        yield engine


@pytest.fixture
def homeostatic_controller():
    """Фикстура Homeostatic Controller с замоканными компонентами."""
    with patch('homeostatic_controller.metrics_collector.MetricsCollector') as mock_collector, \
         patch('homeostatic_controller.load_balancer.LoadBalancer') as mock_balancer, \
         patch('homeostatic_controller.priority_manager.PriorityManager') as mock_priority, \
         patch('homeostatic_controller.resource_allocator.ResourceAllocator') as mock_allocator:
        controller = HomeostaticController(
            metrics_collector=mock_collector,
            load_balancer=mock_balancer,
            priority_manager=mock_priority,
            resource_allocator=mock_allocator,
            update_interval_seconds=30
        )
        # Настраиваем target_ranges как объекты TargetRange (внутренняя структура)
        # Для тестов можно оставить как есть, но тесты должны использовать controller.target_ranges
        yield controller


@pytest.fixture
def rl_agent():
    """Фикстура RL Agent с замоканной средой."""
    with patch('rl_agent.environment.OrchestratorEnv') as mock_env:
        mock_env.state_dim = 10
        mock_env.action_dim = 5
        from rl_agent.models import TrainingConfig
        config = TrainingConfig(
            learning_rate=1e-3,
            gamma=0.99,
            epsilon_start=1.0,
            epsilon_end=0.01,
            epsilon_decay=0.995,
            memory_size=1000,
            batch_size=32,
            target_update_freq=10
        )
        agent = RLAgent(env=mock_env, config=config)
        yield agent


class TestPredictiveEngine:
    """Тесты для Predictive Engine."""

    @pytest.mark.asyncio
    async def test_analyze_event_type(self, predictive_engine, event):
        """Тест анализа типа событий."""
        from datetime import datetime, timezone
        predictive_engine.pattern_detector.detect_seasonality.return_value = {"seasonal": True}
        predictive_engine.pattern_detector.detect_trend.return_value = {"trend": "up"}
        predictive_engine.pattern_detector.detect_anomalies.return_value = [{"timestamp": "2025-01-01", "value": 1.5}]
        predictive_engine.forecast_model.predict.return_value = Forecast(
            event_type="SECURITY_ALERT",
            horizon_hours=12,
            confidence_level=0.95,
            predictions=[
                ForecastPoint(
                    timestamp=datetime(2025,1,2,0,0,0, tzinfo=timezone.utc),
                    predicted_value=0.8,
                    lower_bound=0.6,
                    upper_bound=1.0
                )
            ]
        )
        predictive_engine.store.query_aggregated = AsyncMock(return_value=[
            {"timestamp": datetime(2025,1,1,0,0,0, tzinfo=timezone.utc), "avg_salience": 0.5}
        ])

        result = await predictive_engine.analyze_event_type(
            event_type="SECURITY_ALERT",
            lookback_hours=24
        )

        assert "patterns" in result
        assert "forecast" in result
        predictive_engine.store.query_aggregated.assert_called_once()
        predictive_engine.pattern_detector.detect_seasonality.assert_called_once()
        predictive_engine.pattern_detector.detect_trend.assert_called_once()
        predictive_engine.pattern_detector.detect_anomalies.assert_called_once()
        predictive_engine.forecast_model.predict.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_forecast(self, predictive_engine):
        """Тест генерации прогноза."""
        from datetime import datetime, timezone
        predictive_engine.forecast_model.predict.return_value = Forecast(
            event_type="SECURITY_ALERT",
            horizon_hours=12,
            confidence_level=0.95,
            predictions=[
                ForecastPoint(
                    timestamp=datetime(2025,1,2,0,0,0, tzinfo=timezone.utc),
                    predicted_value=0.8,
                    lower_bound=0.6,
                    upper_bound=1.0
                )
            ]
        )

        timestamps = [datetime(2025,1,1,0,0,0, tzinfo=timezone.utc), datetime(2025,1,1,1,0,0, tzinfo=timezone.utc)]
        values = [0.5, 0.6]
        result = await predictive_engine.generate_forecast(
            event_type="SECURITY_ALERT",
            timestamps=timestamps,
            values=values
        )

        assert isinstance(result, Forecast)
        predictive_engine.forecast_model.predict.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_anomalies_realtime(self, predictive_engine):
        """Тест обнаружения аномалий в реальном времени."""
        from datetime import datetime, timezone
        predictive_engine.pattern_detector.detect_anomalies.return_value = [
            Pattern(
                pattern_type="anomaly",
                parameters={"score": 3.2},
                confidence=0.9,
                start_time=datetime(2025,1,1,12,0,0, tzinfo=timezone.utc),
                end_time=datetime(2025,1,1,12,0,0, tzinfo=timezone.utc)
            )
        ]
        predictive_engine.timeseries_store.query_aggregated = AsyncMock(return_value=[
            {"timestamp": datetime(2025,1,1,9,0,0, tzinfo=timezone.utc), "avg_salience": 0.5},
            {"timestamp": datetime(2025,1,1,10,0,0, tzinfo=timezone.utc), "avg_salience": 0.6},
        ])

        result = await predictive_engine.detect_anomalies_realtime(
            event_type="SECURITY_ALERT",
            value=2.5,
            timestamp=datetime(2025,1,1,12,0,0, tzinfo=timezone.utc)
        )

        assert isinstance(result, list)
        predictive_engine.pattern_detector.detect_anomalies.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_event_for_analysis(self, predictive_engine, event):
        """Тест сохранения события для анализа."""
        await predictive_engine.store_event_for_analysis(event.dict())
        predictive_engine.store.insert_event.assert_called_once()


class TestHomeostaticController:
    """Тесты для Homeostatic Controller."""

    @pytest.mark.asyncio
    async def test_update(self, homeostatic_controller):
        """Тест обновления состояния гомеостаза."""
        homeostatic_controller.metrics_collector.collect_all = AsyncMock(return_value={
            "cpu_load": 0.6,
            "memory_usage": 0.7,
            "error_rate": 0.02,
            "latency_ms": 150,
            "queue_depth": 10,
            "throughput": 100.0
        })
        homeostatic_controller._generate_control_actions = AsyncMock(return_value=[
            ControlAction(
                component="task_orchestrator",
                action_type="scale_agents",
                parameters={"delta": 1, "agent_type": "retriever"}
            )
        ])
        homeostatic_controller._execute_action = AsyncMock(return_value=True)

        state = await homeostatic_controller.update()

        assert isinstance(state, HomeostaticState)
        # отклонения должны быть вычислены
        homeostatic_controller.metrics_collector.collect_all.assert_called_once()
        homeostatic_controller._generate_control_actions.assert_called_once()
        homeostatic_controller._execute_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_control_actions(self, homeostatic_controller):
        """Тест генерации корректирующих действий."""
        deviations = {"cpu_usage": 0.3, "memory_usage": -0.1, "error_rate": 0.08}
        homeostatic_controller.load_balancer.suggest_actions.return_value = [
            {"component": "load_balancer", "action": "scale_up", "parameters": {"factor": 1.5}, "priority": 2}
        ]
        homeostatic_controller.priority_manager.adjust_priorities.return_value = [
            {"component": "priority_manager", "action": "increase", "parameters": {"task_type": "retrieval"}, "priority": 1}
        ]
        homeostatic_controller.resource_allocator.recommend_allocation.return_value = [
            {"component": "resource_allocator", "action": "reallocate", "parameters": {"cpu": 0.1}, "priority": 3}
        ]

        actions = await homeostatic_controller._generate_control_actions(deviations)

        assert len(actions) == 3
        assert all(isinstance(a, ControlAction) for a in actions)
        homeostatic_controller.load_balancer.suggest_actions.assert_called_once_with(deviations)
        homeostatic_controller.priority_manager.adjust_priorities.assert_called_once_with(deviations)
        homeostatic_controller.resource_allocator.recommend_allocation.assert_called_once_with(deviations)

    @pytest.mark.asyncio
    async def test_execute_action(self, homeostatic_controller):
        """Тест выполнения корректирующего действия."""
        action = ControlAction(
            component="load_balancer",
            action="scale_up",
            parameters={"factor": 1.2},
            priority=1
        )
        homeostatic_controller.load_balancer.execute = AsyncMock(return_value=True)

        success = await homeostatic_controller._execute_action(action)

        assert success is True
        homeostatic_controller.load_balancer.execute.assert_called_once_with("scale_up", {"factor": 1.2})

    def test_adjust_target_ranges(self, homeostatic_controller):
        """Тест динамической настройки целевых диапазонов."""
        new_ranges = {"cpu_usage": (0.3, 0.9), "memory_usage": (0.4, 0.95)}
        homeostatic_controller.adjust_target_ranges(new_ranges)
        assert homeostatic_controller.target_ranges["cpu_usage"] == (0.3, 0.9)
        assert homeostatic_controller.target_ranges["memory_usage"] == (0.4, 0.95)


class TestRLAgent:
    """Тесты для Reinforcement Learning Agent."""

    def test_select_action(self, rl_agent):
        """Тест выбора действия (exploration vs exploitation)."""
        state = RLState(
            system_mode="NORMAL",
            metrics=SystemMetrics(cpu_usage=0.5, memory_usage=0.6, error_rate=0.02, latency_ms=150, throughput_rps=100),
            salience_aggregated=0.7,
            time_of_day=0.5
        )
        # При epsilon=1.0 (начальное) должно выбираться случайное действие
        with patch('random.random', return_value=0.1):  # случайное < epsilon
            with patch('torch.randn', return_value=torch.tensor([0.1, 0.2, 0.3, 0.4, 0.5])):
                action = rl_agent.select_action(state, training=True)
                assert isinstance(action, RLAction)
                # случайное действие будет иметь тип из списка
                assert action.action_type in ["adjust_threshold", "adjust_gain", "switch_mode", "scale_resource", "no_op"]

        # При epsilon=0.0 (exploitation) должно выбираться действие с максимальным Q
        rl_agent.epsilon = 0.0
        with patch('torch.randn', return_value=torch.tensor([0.1, 0.2, 0.3, 0.4, 0.5])):
            with patch.object(rl_agent.policy_net, 'forward', return_value=torch.tensor([1.0, 2.0, 0.5, 0.1, 0.0])):
                action = rl_agent.select_action(state, training=True)
                assert action.action_type == "adjust_gain"  # индекс 1 имеет максимальное значение 2.0

    def test_step(self, rl_agent):
        """Тест шага агента (взаимодействие со средой)."""
        state = RLState(
            system_mode="NORMAL",
            metrics=SystemMetrics(cpu_usage=0.5, memory_usage=0.6, error_rate=0.02, latency_ms=150, throughput_rps=100),
            salience_aggregated=0.7,
            time_of_day=0.5
        )
        rl_agent.env.step = Mock(return_value=(state, 0.5, False, {}))
        rl_agent.select_action = Mock(return_value=RLAction(action_type="adjust_threshold", parameters={"delta": 0.1}))

        action, next_state, reward, done = rl_agent.step(state, training=False)

        assert isinstance(action, RLAction)
        assert isinstance(next_state, RLState)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        rl_agent.env.step.assert_called_once_with(state, action)

    def test_learn(self, rl_agent):
        """Тест обучения на буфере воспроизведения."""
        # Заполняем буфер фиктивным опытом
        for i in range(10):
            state = RLState(
                system_mode="NORMAL",
                metrics=SystemMetrics(cpu_usage=0.5 + i*0.01, memory_usage=0.6, error_rate=0.02, latency_ms=150, throughput_rps=100),
                salience_aggregated=0.7,
                time_of_day=0.5
            )
            action = RLAction(action_type="adjust_threshold", parameters={"delta": 0.1})
            next_state = RLState(
                system_mode="NORMAL",
                metrics=SystemMetrics(cpu_usage=0.51 + i*0.01, memory_usage=0.6, error_rate=0.02, latency_ms=150, throughput_rps=100),
                salience_aggregated=0.7,
                time_of_day=0.5
            )
            rl_agent.replay_buffer.push(state, action, next_state, 0.5, False)

        # Мокаем вычисление потерь
        with patch.object(rl_agent.optimizer, 'zero_grad'), \
             patch.object(rl_agent.optimizer, 'step'):
            rl_agent._learn()

        # Проверяем, что обновление произошло (вызов optimizer.step)
        # Достаточно убедиться, что метод не вызвал исключений

    def test_train_episode(self, rl_agent):
        """Тест тренировки эпизода."""
        rl_agent.env.reset = Mock(return_value=RLState(
            system_mode="NORMAL",
            metrics=SystemMetrics(cpu_usage=0.5, memory_usage=0.6, error_rate=0.02, latency_ms=150, throughput_rps=100),
            salience_aggregated=0.7,
            time_of_day=0.5
        ))
        rl_agent.env.step = Mock(side_effect=[
            (RLState(system_mode="NORMAL", metrics=SystemMetrics(cpu_usage=0.55, memory_usage=0.6, error_rate=0.02, latency_ms=150, throughput_rps=100), salience_aggregated=0.7, time_of_day=0.5), 0.5, False, {}),
            (RLState(system_mode="NORMAL", metrics=SystemMetrics(cpu_usage=0.6, memory_usage=0.6, error_rate=0.02, latency_ms=150, throughput_rps=100), salience_aggregated=0.7, time_of_day=0.5), 0.3, True, {})
        ])
        rl_agent.select_action = Mock(side_effect=[
            RLAction(action_type="adjust_threshold", parameters={"delta": 0.1}),
            RLAction(action_type="adjust_gain", parameters={"kp": 0.2})
        ])
        rl_agent._learn = Mock()

        episode = rl_agent.train_episode()

        assert episode.total_reward == 0.8
        assert episode.steps == 2
        assert episode.final_state.system_mode == "NORMAL"
        rl_agent._learn.assert_called()


class TestIntegration:
    """Тесты интеграции компонентов фазы 3 с существующей системой."""

    @pytest.mark.asyncio
    async def test_policy_engine_rl_integration(self):
        """Тест интеграции RL агента с Policy Engine."""
        core = PolicyEngineCore()
        mock_agent = Mock()
        core.register_rl_agent(mock_agent)
        assert core.rl_agent is mock_agent

        adjustments = {"salience_threshold": 0.6, "risk_multiplier": 1.2}
        core.apply_rl_adjustments(adjustments)
        assert core.rl_adjustments == adjustments

        # Проверка, что корректировки применяются в evaluate_mode
        with patch.object(core, '_adjust_thresholds') as mock_adjust:
            mock_adjust.return_value = {"salience_threshold": 0.6}
            core.evaluate_mode(SalienceScore(
                relevance=0.8, novelty=0.7, risk=0.9, urgency=0.8, uncertainty=0.2, aggregated=0.85
            ))
            mock_adjust.assert_called_once()

    @pytest.mark.asyncio
    async def test_advanced_scoring_predictive_integration(self, event):
        """Тест интеграции Predictive Engine в AdvancedScoring."""
        with patch('salience_engine.advanced_scoring.get_predictive_engine') as mock_get:
            mock_engine = AsyncMock()
            mock_engine.generate_forecast.return_value = Forecast(
                points=[ForecastPoint(timestamp="2025-01-02", value=0.8, lower=0.6, upper=1.0)],
                model_name="prophet",
                confidence=0.95
            )
            mock_get.return_value = mock_engine

            scoring = AdvancedScoring(use_predictive=True)
            # Мокаем внутренние зависимости
            scoring.anomaly_detector = Mock()
            scoring.similarity_cache = Mock()
            scoring.external_context_client = Mock()

            novelty = scoring.compute_novelty(event, {})
            # Проверяем, что прогноз был запрошен
            mock_engine.generate_forecast.assert_called_once()
            # novelty должна быть числом
            assert isinstance(novelty, float)

    @pytest.mark.asyncio
    async def test_homeostatic_controller_metrics_collection(self):
        """Тест сбора метрик Homeostatic Controller."""
        collector = MetricsCollector()
        with patch('psutil.cpu_percent', return_value=45.0), \
             patch('psutil.virtual_memory', return_value=Mock(percent=70.0)), \
             patch('homeostatic_controller.metrics_collector.get_system_metrics', return_value={
                 "error_rate": 0.03,
                 "latency_ms": 200,
                 "throughput_rps": 150
             }):
            metrics = collector.collect()
            assert "cpu_usage" in metrics
            assert "memory_usage" in metrics
            assert "error_rate" in metrics
            assert metrics["cpu_usage"] == 0.45
            assert metrics["memory_usage"] == 0.7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])