"""Tests de la configuration (bot/config.py) : socle commun des fixtures de test.

Ces tests restent dans le périmètre du lot 1 : ils garantissent qu'aucun test
ne peut toucher la vraie ``bot.db`` ni utiliser de secret réel.
"""

from __future__ import annotations

from pathlib import Path

import pytest  # type: ignore[import-untyped]

from bot.config import ConfigError, load_config

USER_ID_STR = "424242424242424242"


def _write_config(tmp_path: Path) -> Path:
    """Écrit un config.yaml minimal de test pointant vers une base temporaire."""
    config_file = tmp_path / "config.yaml"
    db_path = tmp_path / "base-de-test.db"
    config_file.write_text(
        "\n".join(
            [
                "memoire:",
                "  court_terme_max_messages: 30",
                "llm:",
                "  model: modele-de-test",
                "  max_tokens: 128",
                "db:",
                f"  path: '{db_path.as_posix()}'",
            ]
        ),
        encoding="utf-8",
    )
    return config_file


def _full_env() -> dict[str, str]:
    """Variables d'environnement factices pour la configuration de test."""
    return {
        "DISCORD_TOKEN": "jeton-de-test-factice",
        "DISCORD_USER_ID": USER_ID_STR,
        "GROQ_API_KEY": "cle-de-test-factice",
    }


def test_load_config_uses_temporary_database(tmp_path: Path) -> None:
    """Vérifie que la base de test pointe vers tmp_path, jamais vers bot.db."""
    config_file = _write_config(tmp_path)
    settings = load_config(config_file, env=_full_env())
    assert settings.db_path == (tmp_path / "base-de-test.db")
    assert settings.db_path.name != "bot.db"
    assert settings.discord_user_id == int(USER_ID_STR)


def test_load_config_requires_secrets(tmp_path: Path) -> None:
    """Vérifie la sécurité : un jeton Discord manquant fait échouer le chargement."""
    config_file = _write_config(tmp_path)
    env = dict(_full_env())
    del env["DISCORD_TOKEN"]
    with pytest.raises(ConfigError):
        load_config(config_file, env=env)


def test_load_config_rejects_non_numeric_user_id(tmp_path: Path) -> None:
    """Vérifie la sécurité : un identifiant utilisateur non numérique est refusé."""
    config_file = _write_config(tmp_path)
    env = dict(_full_env())
    env["DISCORD_USER_ID"] = "scotobi"
    with pytest.raises(ConfigError):
        load_config(config_file, env=env)