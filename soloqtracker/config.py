"""Configuration du tracker LoL temps réel.

Charge les variables depuis le fichier ``.env`` du répertoire racine et
expose une dataclass :class:`Config` typée pour le reste de l'application.
Aucune valeur sensible n'est hardcodée : tout vient de l'environnement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


class ConfigError(Exception):
    """Erreur de configuration : variable manquante ou invalide."""


@dataclass
class Config:
    """Paramètres d'exécution du tracker.

    Attributes:
        riot_api_key: Clé d'API Riot (RIOT_API_KEY).
        riot_region: Région de routage Riot (défaut ``euw1``).
        discord_token: Token du bot Discord (DISCORD_TOKEN).
        discord_channel_id: ID du channel Discord cible.
        tracked_puuids: Liste des PUUIDs des comptes suivis.
        watcher_interval: Intervalle de poll du Watcher (secondes).
        db_path: Chemin du fichier SQLite.
    """

    riot_api_key: str
    discord_token: str
    discord_channel_id: int
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
            "Vérifiez le fichier .env (voir .env.example)."
        )
    return value


def _env_int(name: str) -> int:
    """Convertit une variable d'environnement en entier (strict)."""
    raw = os.getenv(name)
    if raw is None:
        raise ConfigError(f"Variable d'environnement manquante : {name}")
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Variable {name} invalide : {raw!r}") from exc


def load_config() -> Config:
    """Charge la configuration depuis l'environnement / le fichier ``.env``.

    Returns:
        Une instance :class:`Config` prête à l'emploi.

    Raises:
        ConfigError: Si une variable obligatoire (``RIOT_API_KEY``,
            ``DISCORD_TOKEN``) est absente, ou si une valeur numérique
            est invalide.
    """
    load_dotenv()

    riot_api_key = _require("RIOT_API_KEY")
    discord_token = _require("DISCORD_TOKEN")

    discord_channel_id = _env_int("DISCORD_CHANNEL_ID")

    tracked_raw = os.getenv("TRACKED_PUUIDS", "")
    tracked_puuids = [p.strip() for p in tracked_raw.split(",") if p.strip()]

    return Config(
        riot_api_key=riot_api_key,
        riot_region=os.getenv("RIOT_REGION", "euw1"),
        discord_token=discord_token,
        discord_channel_id=discord_channel_id,
        tracked_puuids=tracked_puuids,
        watcher_interval=int(os.getenv("WATCHER_INTERVAL", "60")),
        db_path=os.getenv("DB_PATH", "tracker.db"),
    )