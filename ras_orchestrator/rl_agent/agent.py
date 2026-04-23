"""
Основной RL агент, использующий DQN/PPO для динамической настройки порогов.
"""

import logging
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from datetime import datetime
from common.models import RLState, RLAction
from .environment import OrchestratorEnv
from .models import TrainingConfig, Episode

logger = logging.getLogger(__name__)


class DQNNetwork(nn.Module):
    """Нейронная сеть для DQN."""

    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.fc1 = nn.Linear(state_dim, 128)
        self.fc2 = nn.Linear(128, 128)
        self.fc3 = nn.Linear(128, action_dim)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.fc3(x)


class ReplayBuffer:
    """Буфер воспроизведения для опыта."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.buffer: List[Tuple[np.ndarray, int, float, np.ndarray, bool]] = []
        self.position = 0

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ):
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        self.buffer[self.position] = (state, action, reward, next_state, done)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size: int):
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        states, actions, rewards, next_states, dones = zip(*[self.buffer[i] for i in indices])
        return (
            np.array(states),
            np.array(actions),
            np.array(rewards),
            np.array(next_states),
            np.array(dones),
        )

    def __len__(self):
        return len(self.buffer)


class RLAgent:
    """Агент с обучением с подкреплением."""

    def __init__(
        self,
        env: OrchestratorEnv,
        config: Optional[TrainingConfig] = None,
        use_gpu: bool = False,
    ):
        self.env = env
        self.config = config or TrainingConfig()
        self.device = torch.device("cuda" if use_gpu and torch.cuda.is_available() else "cpu")

        # Нейронные сети
        self.policy_net = DQNNetwork(env.state_dim, env.action_dim).to(self.device)
        self.target_net = DQNNetwork(env.state_dim, env.action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.config.learning_rate)
        self.memory = ReplayBuffer(self.config.memory_size)

        # Параметры exploration
        self.epsilon = self.config.epsilon_start
        self.steps_done = 0

        # Трекинг
        self.episodes: List[Episode] = []
        self.current_episode: Optional[Episode] = None

    def select_action(self, state: RLState, training: bool = True) -> RLAction:
        """Выбирает действие на основе текущей политики."""
        state_vec = self.env.get_state_vector(state)
        state_tensor = torch.FloatTensor(state_vec).unsqueeze(0).to(self.device)

        if training and np.random.random() < self.epsilon:
            # Случайное действие (exploration)
            action_idx = np.random.randint(self.env.action_dim)
        else:
            # Действие от политики (exploitation)
            with torch.no_grad():
                q_values = self.policy_net(state_tensor)
                action_idx = q_values.argmax().item()

        # Преобразуем индекс в действие
        action_type = self._index_to_action_type(action_idx)
        parameters = self._default_parameters(action_type)
        return RLAction(action_type=action_type, parameters=parameters)

    def _index_to_action_type(self, index: int) -> str:
        """Сопоставляет индекс с типом действия."""
        action_types = [
            "adjust_salience_weights",
            "adjust_mode_thresholds",
            "adjust_interrupt_thresholds",
        ]
        return action_types[index % len(action_types)]

    def _default_parameters(self, action_type: str) -> Dict[str, float]:
        """Возвращает параметры по умолчанию для действия."""
        if action_type == "adjust_salience_weights":
            return {"delta": 0.05}
        elif action_type == "adjust_mode_thresholds":
            return {"mode": "NORMAL", "delta": 0.02}
        elif action_type == "adjust_interrupt_thresholds":
            return {"delta": 0.03}
        return {}

    def step(self, state: RLState, training: bool = True) -> Tuple[RLAction, RLState, float, bool]:
        """Выполняет один шаг в среде."""
        action = self.select_action(state, training)
        next_state, reward, done, info = self.env.step(action)

        if training:
            # Сохраняем в буфер воспроизведения
            state_vec = self.env.get_state_vector(state)
            next_state_vec = self.env.get_state_vector(next_state)
            action_idx = self.env.get_action_index(action)
            self.memory.push(state_vec, action_idx, reward, next_state_vec, done)

            # Обновляем epsilon
            self.epsilon = max(
                self.config.epsilon_end,
                self.config.epsilon_start * (self.config.epsilon_decay ** self.steps_done),
            )
            self.steps_done += 1

            # Периодическое обучение
            if len(self.memory) >= self.config.batch_size:
                self._learn()

        return action, next_state, reward, done

    def _learn(self):
        """Выполняет один шаг обучения на мини-батче."""
        if len(self.memory) < self.config.batch_size:
            return

        states, actions, rewards, next_states, dones = self.memory.sample(self.config.batch_size)

        states = torch.FloatTensor(states).to(self.device)
        actions = torch.LongTensor(actions).unsqueeze(1).to(self.device)
        rewards = torch.FloatTensor(rewards).unsqueeze(1).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).unsqueeze(1).to(self.device)

        # Вычисляем Q значения
        q_values = self.policy_net(states).gather(1, actions)
        next_q_values = self.target_net(next_states).max(1)[0].unsqueeze(1)
        expected_q_values = rewards + (self.config.gamma * next_q_values * (1 - dones))

        # Ошибка
        loss = nn.MSELoss()(q_values, expected_q_values.detach())

        # Оптимизация
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        # Периодическое обновление целевой сети
        if self.steps_done % self.config.target_update_frequency == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

    def train_episode(self) -> Episode:
        """Обучает один эпизод и возвращает статистику."""
        state = self.env.reset()
        episode_reward = 0.0
        steps = []
        start_time = datetime.utcnow()

        self.current_episode = Episode(
            episode_id=f"ep_{len(self.episodes)}_{start_time.timestamp()}",
            start_time=start_time,
        )

        for step in range(self.config.max_episode_length):
            action, next_state, reward, done = self.step(state, training=True)
            episode_reward += reward
            steps.append({
                "step": step,
                "action": action.dict(),
                "reward": reward,
                "state": state.dict(),
            })
            state = next_state
            if done:
                break

        end_time = datetime.utcnow()
        episode = Episode(
            episode_id=self.current_episode.episode_id,
            start_time=start_time,
            end_time=end_time,
            steps=steps,
            total_reward=episode_reward,
            metadata={
                "epsilon": self.epsilon,
                "steps_done": self.steps_done,
                "memory_size": len(self.memory),
            },
        )
        self.episodes.append(episode)
        logger.info(f"Episode {len(self.episodes)} finished with reward {episode_reward:.2f}")
        return episode

    def evaluate(self, num_episodes: int = 5) -> Dict[str, Any]:
        """Оценивает производительность агента без exploration."""
        rewards = []
        for _ in range(num_episodes):
            state = self.env.reset()
            episode_reward = 0.0
            for _ in range(self.config.max_episode_length):
                action = self.select_action(state, training=False)
                state, reward, done, _ = self.env.step(action)
                episode_reward += reward
                if done:
                    break
            rewards.append(episode_reward)

        return {
            "mean_reward": np.mean(rewards),
            "std_reward": np.std(rewards),
            "min_reward": np.min(rewards),
            "max_reward": np.max(rewards),
        }

    def save_checkpoint(self, path: str):
        """Сохраняет чекпоинт модели."""
        checkpoint = {
            "policy_net_state_dict": self.policy_net.state_dict(),
            "target_net_state_dict": self.target_net.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "epsilon": self.epsilon,
            "steps_done": self.steps_done,
            "config": self.config.dict(),
            "episodes_count": len(self.episodes),
        }
        torch.save(checkpoint, path)
        logger.info(f"Checkpoint saved to {path}")

    def load_checkpoint(self, path: str):
        """Загружает чекпоинт модели."""
        checkpoint = torch.load(path, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint["policy_net_state_dict"])
        self.target_net.load_state_dict(checkpoint["target_net_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.epsilon = checkpoint["epsilon"]
        self.steps_done = checkpoint["steps_done"]
        logger.info(f"Checkpoint loaded from {path}")