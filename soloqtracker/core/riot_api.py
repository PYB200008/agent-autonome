"""Wrapper asynchrone autour de l'API Riot (httpx + tenacity).

Fournit un client httpx asynchrone avec :
  - throttling respectant les rate limits de la clé dev
    (20 requêtes / seconde, 100 requêtes / 2 minutes),
  - retry avec backoff exponentiel sur les erreurs 429 et 5xx (tenacity),
  - levée d'une exception ``RiotAPIError`` pour les erreurs non récupérables.

La clé API est passée au constructeur (lue depuis l'environnement par
``config.py``, jamais en dur).
"""

import asyncio
import time
from collections import deque
from typing import Optional
from urllib.parse import quote

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Base URLs par région de routage
BASE_URLS = {
    "euw1": "https://euw1.api.riotgames.com",
    "europe": "https://europe.api.riotgames.com",
}

# La route Match-V5 est servie par la plateforme régionale de match (Europe)
MATCH_ROUTING_REGION = "europe"

# Rate limits de la clé de développement
MAX_REQ_PER_SECOND = 20
MAX_REQ_PER_2MIN = 100
WINDOW_2MIN_SECONDS = 120.0
WINDOW_SECOND_SECONDS = 1.0

# Retry
MAX_RETRY_ATTEMPTS = 5
DEFAULT_TIMEOUT = 15.0


class RiotAPIError(Exception):
    """Erreur définitive de l'API Riot (non récupérable par un retry)."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Riot API error {status_code}: {message}")


class _RetryableHTTPError(Exception):
    """Erreur HTTP récupérable (429 ou 5xx) déclenchant le retry tenacity."""

    def __init__(self, status_code: int, reason: str):
        self.status_code = status_code
        self.reason = reason
        super().__init__(f"retryable HTTP error {status_code}: {reason}")


class RiotAPI:
    """Client asynchrone pour l'API Riot Game.

    Usage :
        async with RiotAPI(api_key) as riot:
            account = await riot.get_account_by_riot_id("Summoner", "EUW")
    """

    def __init__(self, api_key: str, region: str = "euw1"):
        """Initialise le client httpx avec le header d'authentification.

        :param api_key: clé d'API Riot (RIOT_API_KEY, jamais en dur).
        :param region: région de routage (ex: euw1).
        """
        self._region = region
        self._base_url = BASE_URLS[region]
        self._match_base_url = BASE_URLS[MATCH_ROUTING_REGION]
        self._client = httpx.AsyncClient(
            headers={"X-Riot-Token": api_key},
            timeout=DEFAULT_TIMEOUT,
        )
        self._timestamps: deque[float] = deque(maxlen=MAX_REQ_PER_2MIN)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    async def _wait_if_needed(self) -> None:
        """Attend avant d'émettre une requête si une limite est atteinte.

        Fenêtres glissantes : 20 requêtes / seconde et 100 / 2 minutes.
        """
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] >= WINDOW_2MIN_SECONDS:
            self._timestamps.popleft()

        if len(self._timestamps) >= MAX_REQ_PER_2MIN:
            oldest = self._timestamps[0]
            wait = oldest + WINDOW_2MIN_SECONDS - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)

        while (
            sum(
                1
                for t in self._timestamps
                if time.monotonic() - t < WINDOW_SECOND_SECONDS
            )
            >= MAX_REQ_PER_SECOND
        ):
            await asyncio.sleep(0.05)

    # ------------------------------------------------------------------
    # Couche bas niveau
    # ------------------------------------------------------------------
    @retry(
        retry=retry_if_exception_type(_RetryableHTTPError),
        wait=wait_exponential(multiplier=2, exp_base=2, min=2, max=60),
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        reraise=True,
    )
    async def _send(
        self, method: str, url: str, params: Optional[dict] = None
    ) -> httpx.Response:
        """Lance une requête après throttling, avec retry sur 429/5xx."""
        await self._wait_if_needed()
        self._timestamps.append(time.monotonic())
        response = await self._client.request(method, url, params=params)
        if response.status_code == 429 or response.status_code >= 500:
            raise _RetryableHTTPError(response.status_code, response.text)
        return response

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        *,
        not_found_ok: bool = False,
    ):
        """Exécute une requête et transforme les erreurs en RiotAPIError."""
        try:
            response = await self._send(method, url, params=params)
        except _RetryableHTTPError as exc:
            raise RiotAPIError(exc.status_code, exc.reason) from exc

        if response.status_code == 404 and not_found_ok:
            return None
        if response.status_code >= 400:
            raise RiotAPIError(
                response.status_code, response.text or response.reason_phrase
            )
        return response.json()

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------
    async def get_account_by_riot_id(self, game_name: str, tag_line: str) -> dict:
        """Résout un Riot ID en compte Riot (Account-V1).

        :return: dict contenant notamment ``puuid`` et ``gameName``.
        """
        name = quote(game_name)
        tag = quote(tag_line)
        url = (
            f"{self._base_url}/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
        )
        return await self._request("GET", url)

    async def get_summoner_by_puuid(self, puuid: str) -> dict:
        """Récupère le profil summoner à partir d'un PUUID (Summoner-V4).

        :return: dict contenant ``id`` (summonerId) et ``accountId``.
        """
        url = (
            f"{self._base_url}/lol/summoner/v4/summoners/by-puuid/{quote(puuid)}"
        )
        return await self._request("GET", url)

    async def get_active_game(self, summoner_id: str) -> Optional[dict]:
        """Récupère la partie en cours d'un joueur (Spectator-V5).

        :return: dict de la game en cours, ou None si le joueur ne joue pas.
        """
        url = (
            f"{self._base_url}/lol/spectator/v5/active-games/by-summoner/"
            f"{quote(summoner_id)}"
        )
        return await self._request("GET", url, not_found_ok=True)

    async def get_match(self, match_id: str) -> dict:
        """Récupère les données détaillées d'un match (Match-V5)."""
        url = f"{self._match_base_url}/lol/match/v5/matches/{quote(match_id)}"
        return await self._request("GET", url)

    async def get_match_history(self, puuid: str, count: int = 5) -> list[str]:
        """Récupère les matchIds récents d'un joueur (Match-V5).

        :param puuid: identifiant universel du joueur.
        :param count: nombre de matchs à récupérer.
        :return: liste de matchIds (du plus récent au plus ancien).
        """
        url = (
            f"{self._match_base_url}/lol/match/v5/matches/by-puuid/"
            f"{quote(puuid)}/ids"
        )
        return await self._request("GET", url, params={"count": count})

    async def get_league_entries(self, summoner_id: str) -> list[dict]:
        """Récupère les entrées de classement d'un summoner (League-V4).

        :return: liste de dicts (solo/duo, flex, etc.) pour le summoner.
        """
        url = (
            f"{self._base_url}/lol/league/v4/entries/by-summoner/"
            f"{quote(summoner_id)}"
        )
        return await self._request("GET", url)

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    async def close(self) -> None:
        """Ferme le client httpx asynchrone."""
        await self._client.aclose()

    async def __aenter__(self) -> "RiotAPI":
        """Entre dans le contexte (utilisable avec ``async with``)."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ferme le client en quittant le contexte."""
        await self.close()