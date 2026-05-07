from abc import ABC, abstractmethod
from loguru import logger


class BaseCollector(ABC):
    """Classe abstraite pour tous les collecteurs de données."""

    name: str = "base"

    @abstractmethod
    async def collect(self, dry_run: bool = False) -> int:
        """Lance la collecte. Retourne le nombre de prospects ingérés."""
        ...

    def log_start(self):
        logger.info(f"[{self.name}] Starting collection")

    def log_done(self, count: int):
        logger.success(f"[{self.name}] Done — {count} prospects ingested")
