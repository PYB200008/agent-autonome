"""Chargement et validation de la configuration.

Les secrets viennent de l'environnement (.env chargé par python-dotenv dans
``main.py``) ; les seuils et chemins viennent de ``config.yaml``, source
opérationnelle. ``DEFAULT_CONFIG`` ne fournit qu'un secours de fusion pour les
clés absentes du YAML : pour changer un seuil, modifier ``config.yaml``, jamais
ce module. Aucune valeur de seuil n'est codée en dur dans les autres modules.

Note de migration (décision utilisateur) : le fournisseur LLM est Groq, la clé
est lue dans ``GROQ_API_KEY`` (l'ancienne ``ANTHROPIC_API_KEY`` n'est plus
utilisée). Le point d'accès et le modèle se configurent dans ``config.yaml``
(section ``llm``), sans toucher au code (exigence R8).
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
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "base_url": "https://api.groq.com/openai/v1",
        "max_tokens": 600,
    },
    "rythme": {
        "delai_min_secondes": 3,
        "delai_max_secondes": 60,
        "poids_longueur": 0.6,
        "longueur_reference": 400,
        "attente_regroupement_secondes": 3,
        "max_messages_reponse": 3,
        "max_longueur_message": 300,
        "intervalle_segments_secondes": 2,
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
REQUIRED_ENV_VARS: tuple[str, ...] = ("DISCORD_TOKEN", "DISCORD_USER_ID", "GROQ_API_KEY")


class ConfigError(Exception):
    """Configuration invalide : secret manquant, fichier absent, valeur incohérente."""


@dataclass(frozen=True)
class Settings:
    """Configuration résolue du bot. Ne contient aucun secret loggé."""

    discord_token: str
    discord_user_id: int
    groq_api_key: str
    memory_max_messages: int
    llm_provider: str
    llm_model: str
    llm_base_url: str
    llm_max_tokens: int
    rythme_delai_min_secondes: float
    rythme_delai_max_secondes: float
    rythme_poids_longueur: float
    rythme_longueur_reference: int
    rythme_attente_regroupement_secondes: float
    rythme_max_messages_reponse: int
    rythme_max_longueur_message: int
    rythme_intervalle_segments_secondes: float
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
    groq_api_key = _required_env("GROQ_API_KEY", environ)
    try:
        discord_user_id = int(_required_env("DISCORD_USER_ID", environ))
    except ValueError:
        raise ConfigError("DISCORD_USER_ID doit être un identifiant numérique") from None
    if discord_user_id <= 0:
        raise ConfigError("DISCORD_USER_ID doit être un identifiant positif")

    memory_max_messages = int(merged["memoire"]["court_terme_max_messages"])
    if memory_max_messages <= 0:
        raise ConfigError("memoire.court_terme_max_messages doit être strictement positif")

    llm_provider = str(merged["llm"]["provider"]).strip()
    if not llm_provider:
        raise ConfigError("llm.provider ne peut pas être vide")
    llm_model = str(merged["llm"]["model"]).strip()
    if not llm_model:
        raise ConfigError("llm.model ne peut pas être vide")
    llm_base_url = str(merged["llm"]["base_url"]).strip()
    if not llm_base_url:
        raise ConfigError("llm.base_url ne peut pas être vide")
    llm_max_tokens = int(merged["llm"]["max_tokens"])
    if llm_max_tokens <= 0:
        raise ConfigError("llm.max_tokens doit être strictement positif")

    # Rythme de réponse (lot 2, S1-S3, S8) : délais, découpage, regroupement.
    rythme_delai_min = float(merged["rythme"]["delai_min_secondes"])
    rythme_delai_max = float(merged["rythme"]["delai_max_secondes"])
    if not (0.0 <= rythme_delai_min < rythme_delai_max):
        raise ConfigError(
            "rythme.delai_min_secondes doit être >= 0 et inférieur à rythme.delai_max_secondes"
        )
    rythme_poids_longueur = float(merged["rythme"]["poids_longueur"])
    if not (0.0 <= rythme_poids_longueur <= 1.0):
        raise ConfigError("rythme.poids_longueur doit être compris entre 0 et 1")
    rythme_longueur_reference = int(merged["rythme"]["longueur_reference"])
    if rythme_longueur_reference <= 0:
        raise ConfigError("rythme.longueur_reference doit être strictement positif")
    rythme_attente_regroupement = float(merged["rythme"]["attente_regroupement_secondes"])
    if rythme_attente_regroupement < 0:
        raise ConfigError("rythme.attente_regroupement_secondes doit être >= 0")
    rythme_max_messages = int(merged["rythme"]["max_messages_reponse"])
    if rythme_max_messages <= 0:
        raise ConfigError("rythme.max_messages_reponse doit être strictement positif")
    rythme_max_longueur = int(merged["rythme"]["max_longueur_message"])
    if rythme_max_longueur <= 0:
        raise ConfigError("rythme.max_longueur_message doit être strictement positif")
    rythme_intervalle_segments = float(merged["rythme"]["intervalle_segments_secondes"])
    if rythme_intervalle_segments < 0:
        raise ConfigError("rythme.intervalle_segments_secondes doit être >= 0")

    base_dir = config_file.parent

    def resolve_path(value: Any) -> Path:
        path = Path(str(value))
        return path if path.is_absolute() else base_dir / path

    return Settings(
        discord_token=discord_token,
        discord_user_id=discord_user_id,
        groq_api_key=groq_api_key,
        memory_max_messages=memory_max_messages,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
        llm_max_tokens=llm_max_tokens,
        rythme_delai_min_secondes=rythme_delai_min,
        rythme_delai_max_secondes=rythme_delai_max,
        rythme_poids_longueur=rythme_poids_longueur,
        rythme_longueur_reference=rythme_longueur_reference,
        rythme_attente_regroupement_secondes=rythme_attente_regroupement,
        rythme_max_messages_reponse=rythme_max_messages,
        rythme_max_longueur_message=rythme_max_longueur,
        rythme_intervalle_segments_secondes=rythme_intervalle_segments,
        db_path=resolve_path(merged["db"]["path"]),
        persona_path=resolve_path(merged["prompts"]["persona_path"]),
        conversation_prompt_path=resolve_path(merged["prompts"]["conversation_path"]),
    )