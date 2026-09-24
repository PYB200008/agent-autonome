"""Chargement et validation de la configuration.

Les secrets viennent de l'environnement (.env chargé par python-dotenv dans
``main.py``) ; les seuils et chemins viennent de ``config.yaml``, source
opérationnelle. ``DEFAULT_CONFIG`` ne fournit qu'un secours de fusion pour les
clés absentes du YAML : pour changer un seuil, modifier ``config.yaml``, jamais
ce module. Aucune valeur de seuil n'est codée en dur dans les autres modules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Secours de fusion pour les clés absentes de config.yaml (source opérationnelle).
DEFAULT_CONFIG: dict[str, Any] = {
    "memoire": {
        "court_terme_max_messages": 30,
    },
    "llm": {
        "model": "claude-haiku-4-5",
        "max_tokens": 600,
    },
    "db": {
        "path": "bot.db",
    },
    "prompts": {
        "persona_path": "persona.md",
        "conversation_path": "prompts/conversation.md",
    },
}

# Variables d'environnement obligatoires (secrets).
REQUIRED_ENV_VARS: tuple[str, ...] = ("DISCORD_TOKEN", "DISCORD_USER_ID", "ANTHROPIC_API_KEY")


class ConfigError(Exception):
    """Configuration invalide : secret manquant, fichier absent, valeur incohérente."""


@dataclass(frozen=True)
class Settings:
    """Configuration résolue du bot. Ne contient aucun secret loggé."""

    discord_token: str
    discord_user_id: int
    anthropic_api_key: str
    memory_max_messages: int
    llm_model: str
    llm_max_tokens: int
    db_path: Path
    persona_path: Path
    conversation_prompt_path: Path


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Fusionne récursivement ``override`` par-dessus ``base``."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _required_env(name: str, env: dict[str, str]) -> str:
    """Renvoie la valeur de la variable d'environnement, ou lève ConfigError."""
    value = env.get(name, "")
    if not value:
        raise ConfigError(f"Variable d'environnement {name} manquante ou vide (voir .env.example)")
    return value


def load_config(config_path: str | Path = "config.yaml", env: dict[str, str] | None = None) -> Settings:
    """Charge la configuration depuis ``config.yaml`` et l'environnement.

    Si ``env`` est fourni (tests), il remplace ``os.environ``.
    Les chemins relatifs du YAML sont résolus par rapport au dossier du fichier
    de configuration, pour que le bot fonctionne quel que soit le répertoire de
    lancement.
    """
    environ = dict(os.environ) if env is None else dict(env)

    config_file = Path(config_path).resolve()
    if not config_file.is_file():
        raise ConfigError(f"Fichier de configuration introuvable : {config_file}")
    with config_file.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    merged = _deep_merge(DEFAULT_CONFIG, raw)

    # Secrets : toujours depuis l'environnement, jamais depuis le YAML.
    discord_token = _required_env("DISCORD_TOKEN", environ)
    anthropic_api_key = _required_env("ANTHROPIC_API_KEY", environ)
    try:
        discord_user_id = int(_required_env("DISCORD_USER_ID", environ))
    except ValueError:
        raise ConfigError("DISCORD_USER_ID doit être un identifiant numérique") from None
    if discord_user_id <= 0:
        raise ConfigError("DISCORD_USER_ID doit être un identifiant positif")

    memory_max_messages = int(merged["memoire"]["court_terme_max_messages"])
    if memory_max_messages <= 0:
        raise ConfigError("memoire.court_terme_max_messages doit être strictement positif")

    llm_model = str(merged["llm"]["model"]).strip()
    if not llm_model:
        raise ConfigError("llm.model ne peut pas être vide")
    llm_max_tokens = int(merged["llm"]["max_tokens"])
    if llm_max_tokens <= 0:
        raise ConfigError("llm.max_tokens doit être strictement positif")

    base_dir = config_file.parent

    def resolve_path(value: Any) -> Path:
        path = Path(str(value))
        return path if path.is_absolute() else base_dir / path

    return Settings(
        discord_token=discord_token,
        discord_user_id=discord_user_id,
        anthropic_api_key=anthropic_api_key,
        memory_max_messages=memory_max_messages,
        llm_model=llm_model,
        llm_max_tokens=llm_max_tokens,
        db_path=resolve_path(merged["db"]["path"]),
        persona_path=resolve_path(merged["prompts"]["persona_path"]),
        conversation_prompt_path=resolve_path(merged["prompts"]["conversation_path"]),
    )