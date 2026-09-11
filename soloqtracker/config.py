"""Configuration du tracker LoL temps r\u00e9el.

Charge les variables depuis le fichier ``.env`` du r\u00e9pertoire racine et
expose une dataclass :class:`Config` typ\u00e9e pour le reste de l'application.
Aucune valeur sensible n'est hardcod\u00e9e : tout vient de l'environnement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


class ConfigError(Exception):
    """Erreur de configuration : variable manquante ou invalide."""


@dataclass
class Config:
    """Param\u00e8tres d'ex\u00e9cution du tracker.

    Attributes:
        riot_api_key: Cl\u00e9 d'API Riot (RIOT_API_KEY).
        riot_region: R\u00e9gion de routage Riot (d\u00e9faut ``euw1``).
        discord_webhook_url: URL du webhook Discord (DISCORD_WEBHOOK_URL).
        tracked_puuids: Liste des PUUIDs des comptes suivis.
        watcher_interval: Intervalle de poll du Watcher (secondes).
        db_path: Chemin du fichier SQLite.
    """

    riot_api_key: str
    discord_webhook_url: str
    tracked_puuids: list[str] = field(default_factory=list)
    riot_region: str = "euw1"
    watcher_interval: int = 60
    db_path: str = "tracker.db"


def _require(name: str) -> str:
    """Renvoie la valeur d'une variable d'environnement obligatoire."""
    value = os.getenv(name)
    if not value:
        raise ConfigError(
            f"Variable d'environnement manquante : {name}. "
            "V\u00e9rifiez le fichier .env (voir .env.example)."
        )
    return value


def load_config() -> Config:
    """Charge la configuration depuis l'environnement / le fichier ``.env``.

    Returns:
        Une instance :class:`Config` pr\u00eate \u00e0 l'emploi.

    Raises:
        ConfigError: Si une variable obligatoire (``RIOT_API_KEY``,
            ``DISCORD_WEBHOOK_URL``) est absente.
    """
    load_dotenv()

    riot_api_key = _require("RIOT_API_KEY")
    discord_webhook_url = _require("DISCORD_WEBHOOK_URL")

    tracked_raw = os.getenv("TRACKED_PUUIDS", "")
    tracked_puuids = [p.strip() for p in tracked_raw.split(",") if p.strip()]

    return Config(
        riot_api_key=riot_api_key,
        riot_region=os.getenv("RIOT_REGION", "euw1"),
        discord_webhook_url=discord_webhook_url,
        tracked_puuids=tracked_puuids,
        watcher_interval=int(os.getenv("WATCHER_INTERVAL", "60")),
        db_path=os.getenv("DB_PATH", "tracker.db"),
    )
