"""Strategies registry."""
from app.modules.recommender.strategies.base import RecommendationStrategy, LearnerContext, ScoredItem
from app.modules.recommender.strategies.rules import RuleBasedStrategy
from app.modules.recommender.strategies.embeddings import EmbeddingsStrategy
from app.modules.recommender.strategies.collaborative import CollaborativeStrategy

STRATEGY_REGISTRY = {
    "rule_based": RuleBasedStrategy(),
    "embeddings": EmbeddingsStrategy(),
    "collaborative": CollaborativeStrategy(),
}


def register_strategy(strategy: RecommendationStrategy) -> None:
    """Strategy registry: adding a strategy means adding one class and registering it (FR-506)."""
    STRATEGY_REGISTRY[strategy.name] = strategy


__all__ = [
    "RecommendationStrategy",
    "LearnerContext",
    "ScoredItem",
    "RuleBasedStrategy",
    "EmbeddingsStrategy",
    "CollaborativeStrategy",
    "STRATEGY_REGISTRY",
    "register_strategy",
]

