"""
Точка входа для RL Agent.
"""
import warnings
import logging
from .agent import RLAgent
from .environment import OrchestratorEnv

# Подавление RuntimeWarning для модуля rl_agent
warnings.filterwarnings("ignore", category=RuntimeWarning, module="rl_agent")

logger = logging.getLogger(__name__)

def main():
    """Основная функция запуска RL Agent."""
    logger.info("Starting RL Agent...")
    
    # Инициализация окружения и агента
    env = OrchestratorEnv()
    agent = RLAgent(env)
    
    # Запуск обучения (или инференса, в зависимости от конфигурации)
    logger.info("Starting training...")
    episodes = 100
    logger.info(f"Starting training for {episodes} episodes...")
    for episode_idx in range(episodes):
        episode = agent.train_episode()
        if (episode_idx + 1) % 10 == 0:
            logger.info(f"Episode {episode_idx + 1} finished, total reward: {episode.total_reward:.2f}")
    
    # Оценка после обучения
    eval_results = agent.evaluate(num_episodes=5)
    logger.info(f"Evaluation results: {eval_results}")
    
    logger.info("RL Agent finished.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()