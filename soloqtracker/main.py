"""Point d'entr\u00e9e du tracker LoL temps r\u00e9el.

Orchestre les agents : Watcher et MatchFetcher, avec envoi via webhook Discord.

Usage::

    python main.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from config import ConfigError, load_config
from core.discord_webhook import DiscordWebhook
from agents.match_fetcher import MatchFetcher
from agents.watcher import Watcher
from core.db import init_db
from core.riot_api import RiotAPI

logger = logging.getLogger("tracker")


def _setup_logging() -> None:
    """Configure le logging global (format timestamp, niveau INFO)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s \u2502 %(levelname)-7s \u2502 %(name)s \u2502 %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main() -> None:
    """Point d'entr\u00e9e principal : initialise et lance tous les agents."""
    _setup_logging()

    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Configuration invalide : %s", exc)
        sys.exit(1)

    logger.info(
        "Tracker LoL d\u00e9marr\u00e9 \u2014 %d compte(s) suivi(s)",
        len(config.tracked_puuids),
    )
    logger.info(
        "Region : %s | Poll : %ds",
        config.riot_region,
        config.watcher_interval,
    )

    # 1. Base de donn\u00e9es
    conn = init_db(config.db_path)
    logger.info("Base SQLite ouverte : %s", config.db_path)

    # 2. Client API Riot
    riot = RiotAPI(config.riot_api_key, config.riot_region)
    logger.info("Client Riot API initialis\u00e9 (region=%s)", config.riot_region)

    # 3. Webhook Discord
    webhook = DiscordWebhook(config.discord_webhook_url)
    logger.info("Webhook Discord initialis\u00e9")

    # 4. Agents avec callbacks
    watcher = Watcher(
        riot,
        conn,
        config.tracked_puuids,
        config.watcher_interval,
        callback=webhook.send_game_composition,
    )
    fetcher = MatchFetcher(
        riot,
        conn,
        callback=webhook.send_game_result,
    )

    # 5. Lancer tout en parall\u00e8le
    tasks = [
        asyncio.create_task(watcher.start(), name="watcher"),
        asyncio.create_task(fetcher.start(), name="fetcher"),
    ]

    # 6. Gestion de l'arr\u00eat propre (Ctrl+C)
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Signal d'arr\u00eat re\u00e7u \u2014 arr\u00eat en cours\u2026")
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)
    else:
        pass

    try:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            try:
                task.result()
            except asyncio.CancelledError:
                logger.info("T\u00e2che %s annul\u00e9e.", task.get_name())
            except Exception:
                logger.exception(
                    "T\u00e2che %s termin\u00e9e avec erreur.", task.get_name()
                )
    finally:
        logger.info("Arr\u00eat des agents\u2026")
        await watcher.stop()
        await fetcher.stop()
        await webhook.close()
        await riot.close()
        conn.close()
        logger.info("Tracker LoL arr\u00eat\u00e9.")


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
