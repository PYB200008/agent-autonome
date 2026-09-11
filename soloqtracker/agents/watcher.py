"""Agent watcher : détection du début de partie via Spectator-V5.

Ce module poll périodiquement l'API Riot pour chaque PUUID suivi et détecte
l'entrée en partie (game en cours via Spectator-V5). Quand une nouvelle game
est détectée, elle est :
  1. construite par ``parse_game_from_spectator`` (core.models),
  2. enrichie avec les rangs des joueurs (League-V4),
  3. sauvegardée en base (core.db),
  4. notifiée à un callback asynchrone fourni par l'appelant
     (typiquement le bot Discord — le watcher n'a pas connaissance de
     Discord, il expose seulement un hook).

Le watcher est autonome et testable sans dépendre de Discord.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.db import get_active_games, save_game
from core.models import Game, Player, parse_game_from_spectator
from core.riot_api import RiotAPI, RiotAPIError

logger = logging.getLogger(__name__)

# Queue League-V4 correspondant au classement solo/duo
SOLO_QUEUE = "RANKED_SOLO_5x5"


@dataclass
class _PollResult:
    """Résultat du poll d'un PUUID (utile pour les logs/tests)."""

    puuid: str
    game_id: int | None = None
    detected: bool = False


class Watcher:
    """Agent 1 : poll Spectator-V5 et détection des débuts de game.

    Args:
        riot_api: Wrapper asynchrone de l'API Riot.
        db_conn: Connexion SQLite (partagée entre les agents).
        tracked_puuids: PUUIDs des comptes à suivre.
        poll_interval: Intervalle (secondes) entre deux passes de poll.
        callback: Coroutine appelée avec la Game complète quand une
            nouvelle game est détectée.
    """

    def __init__(
        self,
        riot_api: RiotAPI,
        db_conn,
        tracked_puuids: list[str],
        poll_interval: int = 60,
        callback: Callable[[Game], Awaitable[None]] | None = None,
    ):
        self.riot_api = riot_api
        self._db_conn = db_conn
        self.tracked_puuids = list(tracked_puuids)
        self.poll_interval = poll_interval
        self.callback = callback

        # Cache mémoire puuid -> summonerId (plusieurs appels par game).
        self._summoner_cache: dict[str, str] = {}
        # Cache mémoire rang par puuid (stable pendant une game).
        self._rank_cache: dict[str, str] = {}

        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Boucle principale : poll toutes les ``poll_interval`` secondes.

        Tourne en continu jusqu'à ce que ``stop()`` soit appelé.
        """
        logger.info(
            "Watcher démarré : %d compte(s) suivi(s), poll toutes les %ds",
            len(self.tracked_puuids),
            self.poll_interval,
        )

        while not self._stop_event.is_set():
            await self._poll_once()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.poll_interval
                )
            except asyncio.TimeoutError:
                pass

        logger.info("Watcher arrêté")

    async def stop(self) -> None:
        """Demande l'arrêt de la boucle principale."""
        logger.debug("Arrêt demandé")
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Boucle de poll
    # ------------------------------------------------------------------
    async def _poll_once(self) -> None:
        """Vérifie tous les PUUID suivis et notifie les nouvelles games."""
        try:
            active_games = get_active_games(self._db_conn)
        except Exception:
            logger.exception("Erreur de lecture des games actives en base")
            active_games = []

        tracked_game_ids = {g.game_id for g in active_games}

        await asyncio.gather(
            *(
                self._check_puuid(puuid, tracked_game_ids)
                for puuid in self.tracked_puuids
            ),
            return_exceptions=True,
        )

    async def _check_puuid(
        self, puuid: str, tracked_game_ids: set[int]
    ) -> _PollResult:
        """Vérifie la présence en game d'un seul PUUID.

        Les erreurs API d'un joueur sont loggées et n'interrompent pas
        le traitement des autres PUUID (defer à l'appelant via gather).
        """
        try:
            summoner_id = await self._resolve_summoner(puuid)
            game_data = await self.riot_api.get_active_game(summoner_id)
        except RiotAPIError as exc:
            logger.warning("Erreur API pour %s : %s", puuid, exc)
            return _PollResult(puuid)

        if game_data is None:
            return _PollResult(puuid)

        game = parse_game_from_spectator(game_data, puuid)

        if game.game_id in tracked_game_ids:
            logger.debug(
                "Game %d déjà suivie pour %s, ignorée",
                game.game_id,
                puuid,
            )
            return _PollResult(puuid, game.game_id)

        await self._enrich_ranks(game)
        await self._save_and_notify(game)
        logger.info(
            "Nouvelle game %d détectée pour %s (%s)",
            game.game_id,
            puuid,
            game.game_mode,
        )
        return _PollResult(puuid, game.game_id, detected=True)

    # ------------------------------------------------------------------
    # Enrichissement
    # ------------------------------------------------------------------
    async def _enrich_ranks(self, game: Game) -> None:
        """Remplit le rang (League-V4) de chaque participant de la game.

        Pour chaque joueur : puuid -> summonerId -> league entries.
        Les échecs (joueur hors région, erreur API...) laissent le rang
        à ``None`` sans bloquer le traitement.
        """
        for team in game.teams:
            for player in team.players:
                player.rank = await self._fetch_rank(player)

    async def _fetch_rank(self, player: Player) -> str | None:
        """Récupère (et met en cache) le rang d'un joueur, ou None."""
        cached = self._rank_cache.get(player.puuid)
        if cached is not None:
            return cached

        try:
            summoner_id = await self._resolve_summoner(player.puuid)
            entries = await self.riot_api.get_league_entries(summoner_id)
        except RiotAPIError as exc:
            logger.debug(
                "Rang indisponible pour %s (%s) : %s",
                player.summoner_name,
                player.puuid,
                exc,
            )
            return None

        rank = self._format_rank(entries)
        if rank is not None:
            self._rank_cache[player.puuid] = rank
        return rank

    @staticmethod
    def _format_rank(entries: list[dict]) -> str | None:
        """Formate l'entrée ligue en chaîne lisible, ou None.

        Priorise la file solo/duo (RANKED_SOLO_5x5), sinon le premier
        classement disponible.
        """
        if not entries:
            return None

        entry = next(
            (e for e in entries if e.get("queueType") == SOLO_QUEUE), entries[0]
        )
        tier = entry.get("tier")
        rank = entry.get("rank")
        lp = entry.get("leaguePoints")
        if not tier or not rank:
            return None
        return f"{tier} {rank} {int(lp):d} LP"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _resolve_summoner(self, puuid: str) -> str:
        """Résout un PUUID en summonerId (avec cache en mémoire)."""
        cached = self._summoner_cache.get(puuid)
        if cached is not None:
            return cached

        summoner = await self.riot_api.get_summoner_by_puuid(puuid)
        summoner_id = summoner["id"]
        self._summoner_cache[puuid] = summoner_id
        return summoner_id

    async def _save_and_notify(self, game: Game) -> None:
        """Sauvegarde la game en base puis notifie le callback.

        La sauvegarde est toujours effectuée ; si le callback échoue,
        l'erreur est loggée sans empêcher la persistance.
        """
        save_game(self._db_conn, game)

        if self.callback is None:
            return
        try:
            await self.callback(game)
        except Exception:
            logger.exception(
                "Erreur du callback pour la game %d", game.game_id
            )