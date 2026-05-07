"""
Pool de comptes LinkedIn avec rotation round-robin.
3 comptes × 250 req/jour = 750 prospects/jour maximum.
"""
import asyncio
import time
from dataclasses import dataclass, field
from loguru import logger
from collectors.linkedin_client import LinkedInClient
from config.settings import get_settings

settings = get_settings()


@dataclass
class AccountState:
    client: LinkedInClient
    email: str
    requests_today: int = 0
    last_reset: float = field(default_factory=time.time)
    is_healthy: bool = True
    paused_until: float = 0.0


class SessionManager:
    def __init__(self):
        self._clients: list[AccountState] = []
        self._index = 0

    async def initialize(self):
        accounts = []
        for i in range(1, 4):
            email = getattr(settings, f"linkedin_email_{i}", "")
            password = getattr(settings, f"linkedin_password_{i}", "")
            if email and password:
                accounts.append((email, password))

        if not accounts:
            raise RuntimeError("Aucun compte LinkedIn configuré dans .env")

        for email, password in accounts:
            client = LinkedInClient(email, password)
            ok = await client.connect()
            state = AccountState(client=client, email=email, is_healthy=ok)
            self._clients.append(state)
            if ok:
                logger.success(f"Compte prêt: {email}")
            else:
                logger.warning(f"Compte indisponible: {email}")

        healthy = [s for s in self._clients if s.is_healthy]
        if not healthy:
            raise RuntimeError(
                "Aucun compte LinkedIn actif. Vérifiez les credentials et les cookies."
            )
        logger.info(f"Pool de sessions: {len(healthy)}/{len(self._clients)} comptes actifs")

    def get_client(self) -> LinkedInClient:
        now = time.time()
        for _ in range(len(self._clients)):
            state = self._clients[self._index % len(self._clients)]
            self._index += 1

            # Réinitialiser le compteur journalier après 24h
            if now - state.last_reset > 86400:
                state.requests_today = 0
                state.last_reset = now

            if not state.is_healthy:
                continue
            if state.paused_until > now:
                logger.debug(f"Compte {state.email} en pause pour {state.paused_until - now:.0f}s")
                continue
            if state.requests_today >= settings.linkedin_requests_per_day:
                logger.warning(f"Limite journalière atteinte pour {state.email}")
                continue

            state.requests_today += 1
            return state.client

        raise RuntimeError(
            "Tous les comptes LinkedIn sont épuisés ou en pause. Réessayez demain."
        )

    def mark_unhealthy(self, email: str):
        for state in self._clients:
            if state.email == email:
                state.is_healthy = False
                logger.error(f"Compte {email} marqué comme non-sain")

    def pause_account(self, email: str, seconds: int = 86400):
        for state in self._clients:
            if state.email == email:
                state.paused_until = time.time() + seconds
                logger.warning(f"Compte {email} mis en pause pour {seconds}s")

    def get_stats(self) -> dict:
        now = time.time()
        return {
            "total": len(self._clients),
            "healthy": sum(1 for s in self._clients if s.is_healthy),
            "accounts": [
                {
                    "email": s.email,
                    "requests_today": s.requests_today,
                    "healthy": s.is_healthy,
                    "paused": s.paused_until > now,
                    "paused_for_seconds": max(0, s.paused_until - now),
                }
                for s in self._clients
            ],
        }
