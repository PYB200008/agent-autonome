"""Agent 3 — MatchFetcher : stats finales post-game via Match-V5.

Ce module surveille les games enregistrées en base (statut ``IN_PROGRESS``)
et détecte leur fin de manière asynchrone :

  1. il interroge l'historique Match-V5 du joueur suivi (``count=1``) ;
  2. dès que le match le plus récent ressemble à la game suivie (même mode
     de jeu, début de partie cohérent avec ``created_at`` du Game), la game
     est considérée comme finie ;
  3. il récupère le match complet avec ``RiotAPI.get_match()``, le parse via
     ``parse_game_from_match()``, met à jour la base puis notifie via un
     callback (typiquement le bot Discord).

Le fetcher est autonome : il tourne dans sa propre boucle asyncio et peut
être démarré / arrêté avec ``start()`` / ``stop()``.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from core.db import get_active_games, init_db, save_game, update_game_status
from core.models import Game, GameStatus, parse_game_from_match
from core.riot_api import RiotAPI, RiotAPIError

logger = logging.getLogger(__name__)

# Tolérance (secondes) entre le début réel du match (``gameCreation``
# retourné par Match-V5) et le moment où le Watcher a créé le Game en base.
# Le poll du Watcher (~60s) peut décaler ``created_at`` par rapport au vrai
# début de partie : on garde une marge large pour éviter les faux négatifs
# tout en écartant un match plus ancien (partie précédente déjà finie).
GAME_START_TOLERANCE_SECONDS = 600

# Nombre de matchs remontés par get_match_history() à chaque vérification.
HISTORY_COUNT = 1


class MatchFetcher:
    """Surveille les games actives et récupère leurs stats finales.

    Attribut exposé :
        on_game_finished: callback ``async (Game) -> None`` appelé avec le
            Game finalisé à chaque fin de partie détectée.

    Args:
        riot_api: Client asynchrone de l'API Riot.
        db_conn: Connexion SQLite (gérée par ``core.db``).
        poll_interval: secondes entre deux passes de vérification.
        callback: coroutine exécutée avec le Game finalisé (ex: Discord).
    """

    def __init__(
        self,
        riot_api: RiotAPI,
        db_conn,
        poll_interval: int = 30,
        callback: Callable[[Game], Awaitable[None]] | None = None,
    ) -> None:
        self._riot_api = riot_api
        self._db_conn = db_conn
        self._poll_interval = poll_interval
        self._callback = callback
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Démarre la boucle de surveillance des fins de game."""
        if self._task is not None and not self._task.done():
            logger.warning("MatchFetcher déjà en cours d'exécution.")
            return
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "MatchFetcher démarré (poll toutes les %ss).", self._poll_interval
        )

    async def stop(self) -> None:
        """Arrête la boucle de surveillance en cours."""
        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("MatchFetcher arrêté.")

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------
    async def _run_loop(self) -> None:
        """Boucle poll : vérifie les games actives à intervalle régulier."""
        while not self._stop_event.is_set():
            try:
                await self._check_active_games()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Erreur lors de la vérification des games.")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._poll_interval
                )
            except asyncio.TimeoutError:
                continue

    async def _check_active_games(self) -> None:
        """Traite chaque game actif en base, de façon indépendante."""
        games = await self._db_run(get_active_games)
        for game in games or []:
            if game.status is not GameStatus.IN_PROGRESS:
                continue
            try:
                await self._process_game(game)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Game %s : échec du traitement, on continue.",
                    game.game_id,
                )

    # ------------------------------------------------------------------
    # Détection de fin de game
    # ------------------------------------------------------------------
    async def _process_game(self, game: Game) -> None:
        """Détecte la fin de ``game`` puis récupère et persiste les stats."""
        if not game.tracked_player_puuid:
            logger.warning("Game %s sans joueur suivi, ignorée.", game.game_id)
            return

        try:
            finished = await self._find_finished_match(game)
        except RiotAPIError as exc:
            if exc.status_code == 404:
                logger.debug(
                    "Game %s : match non encore disponible, nouvel essai au "
                    "prochain poll (erreur %s).",
                    game.game_id,
                    exc.status_code,
                )
                return
            raise

        if finished is None:
            return

        await self._finalize_game(game, finished)

    async def _find_finished_match(self, game: Game) -> Game | None:
        """Retourne le Game finalisé si la game est finie, sinon None.

        La détection s'appuie sur l'historique Match-V5 du joueur :
          - le match le plus récent devient ``latest_match_id`` ;
          - s'il porte le même ``gameMode`` et un début de partie cohérent
            avec ``created_at``, il est imputé à la game suivie.
        """
        history = await self._riot_api.get_match_history(
            game.tracked_player_puuid, count=HISTORY_COUNT
        )
        if not history:
            return None

        latest_match_id = history[0]
        if game.match_id == latest_match_id:
            logger.debug(
                "Game %s : match %s déjà enregistré.",
                game.game_id,
                latest_match_id,
            )
            return None

        match_data = await self._riot_api.get_match(latest_match_id)
        if not self._looks_like_finished_game(game, match_data):
            return None

        return parse_game_from_match(match_data, game.tracked_player_puuid)

    def _looks_like_finished_game(self, game: Game, match_data: dict) -> bool:
        """Vérifie que le match le plus récent correspond bien à ``game``."""
        info = match_data.get("info", {})
        game_mode = info.get("gameMode")

        if game.game_mode and game_mode != game.game_mode:
            logger.debug(
                "Game %s : mode différent (%s vs %s), match ignoré.",
                game.game_id,
                game_mode,
                game.game_mode,
            )
            return False

        creation_ms = info.get("gameCreation")
        if creation_ms is not None:
            created_at = game.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            delta = abs(creation_ms / 1000.0 - created_at.timestamp())
            if delta > GAME_START_TOLERANCE_SECONDS:
                logger.debug(
                    "Game %s : début du match incohérent (%ss d'écart), "
                    "match ignoré.",
                    game.game_id,
                    int(delta),
                )
                return False

        return True

    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------
    async def _finalize_game(self, game: Game, finished: Game) -> None:
        """Persiste le Game finalisé en base (statut + stats) et notifie."""
        finished.game_id = game.game_id
        finished.tracked_player_puuid = game.tracked_player_puuid
        finished.created_at = game.created_at
        finished.updated_at = datetime.utcnow()

        await self._db_run(save_game, finished)
        await self._db_run(
            update_game_status, finished.game_id, GameStatus.FINISHED
        )

        logger.info("Game %s terminée (match %s).", game.game_id, finished.match_id)

        if self._callback is not None:
            try:
                await self._callback(finished)
            except Exception:
                logger.exception(
                    "Erreur du callback on_game_finished pour la game %s.",
                    finished.game_id,
                )

    # ------------------------------------------------------------------
    # Accès à la couche DB (sync ou async indifféremment)
    # ------------------------------------------------------------------
    async def _db_run(self, func, *args):
        """Exécute un helper de ``core.db``, synchrone ou asynchrone.

        La couche ``core.db`` n'étant pas encore stabilisée, on s'adapte aux
        deux cas pour ne jamais bloquer la boucle asyncio (``to_thread`` si
        la fonction est synchrone).
        """
        if inspect.iscoroutinefunction(func):
            return await func(self._db_conn, *args)
        return await asyncio.to_thread(func, self._db_conn, *args)


__all__ = ["MatchFetcher"]