"""Point d'entrée du tracker LoL temps réel.

Orchestre les agents : Watcher, MatchFetcher et DiscordBot.

Usage::

    python main.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from config import ConfigError, load_config
from agents.discord_bot import DiscordBot
from agents.match_fetcher import MatchFetcher
from agents.watcher import Watcher
from core.db import init_db
from core.riot_api import RiotAPI

logger = logging.getLogger("tracker")


def _setup_logging() -> None:
    """Configure le logging global (format timestamp, niveau INFO)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main() -> None:
    """Point d'entrée principal : initialise et lance tous les agents."""
    _setup_logging()

    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Configuration invalide : %s", exc)
        sys.exit(1)

    logger.info(
        "Tracker LoL démarré — %d compte(s) suivi(s)",
        len(config.tracked_puuids),
    )
    logger.info(
        "Region : %s | Channel Discord : %s | Poll : %ds",
        config.riot_region,
        config.discord_channel_id,
        config.watcher_interval,
    )

    # 1. Base de données
    conn = init_db(config.db_path)
    logger.info("Base SQLite ouverte : %s", config.db_path)

    # 2. Client API Riot
    riot = RiotAPI(config.riot_api_key, config.riot_region)
    logger.info("Client Riot API initialisé (region=%s)", config.riot_region)

    # 3. Bot Discord
    bot = DiscordBot(config.discord_token, config.discord_channel_id)

    # 4. Agents avec callbacks
    watcher = Watcher(
        riot,
        conn,
        config.tracked_puuids,
        config.watcher_interval,
        callback=bot.send_game_composition,
    )
    fetcher = MatchFetcher(
        riot,
        conn,
        callback=bot.send_game_result,
    )

    # 5. Lancer tout en parallèle
    bot_task = await bot.start_as_task()
    tasks = [
        bot_task,
        asyncio.create_task(watcher.start(), name="watcher"),
        asyncio.create_task(fetcher.start(), name="fetcher"),
    ]

    # 6. Gestion de l'arrêt propre (Ctrl+C)
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Signal d'arrêt reçu — arrêt en cours…")
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)
    else:
        # Sur Windows, add_signal_handler n'est pas supporté — on se repose
        # sur KeyboardInterrupt lancé par le runtime asyncio.
        pass

    try:
        # Attendre soit le signal d'arrêt, soit la fin d'une tâche (erreur)
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Logger les tâches terminées
        for task in done:
            try:
                task.result()
            except asyncio.CancelledError:
                logger.info("Tâche %s annulée.", task.get_name())
            except Exception:
                logger.exception(
                    "Tâche %s terminée avec erreur.", task.get_name()
                )
    finally:
        # Arrêt propre de tous les agents
        logger.info("Arrêt des agents…")
        await watcher.stop()
        await fetcher.stop()
        await bot.stop()
        await riot.close()
        conn.close()
        logger.info("Tracker LoL arrêté.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ConfigError as exc:
        logging.basicConfig(
            format="%(levelname)s: %(message)s", level=logging.ERROR
        )
        logging.error("Configuration invalide : %s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
