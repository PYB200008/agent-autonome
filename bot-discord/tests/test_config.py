"""Tests de la configuration (bot/config.py) : socle commun des fixtures de test.

Ces tests restent dans le périmètre du lot 1 : ils garantissent qu'aucun test
ne peut toucher la vraie ``bot.db`` ni utiliser de secret réel.
"""

from __future__ import annotations

from pathlib import Path

import pytest  # type: ignore[import-untyped]

from bot.config import ConfigError, load_config

USER_ID_STR = "424242424242424242"


def _write_config(tmp_path: Path, rythme_section: str = "") -> Path:
    """Écrit un config.yaml minimal de test pointant vers une base temporaire.

    ``rythme_section`` permet d'ajouter (ou de surcharger) la section rythme
    pour tester ses validations ; par défaut la section est absente et les
    valeurs par défaut s'appliquent (S1-S3, S8).
    """
    config_file = tmp_path / "config.yaml"
    db_path = tmp_path / "base-de-test.db"
    content = "\n".join(
        [
            "memoire:",
            "  court_terme_max_messages: 30",
            "llm:",
            "  model: modele-de-test",
            "  max_tokens: 128",
            "db:",
            f"  path: '{db_path.as_posix()}'",
        ]
    )
    if rythme_section:
        content += "\n" + rythme_section
    config_file.write_text(content, encoding="utf-8")
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


def test_rythme_defaults_loaded_when_section_absent(tmp_path: Path) -> None:
    """Vérifie S1, S3 et S8 : sans section rythme dans config.yaml, les valeurs
    par défaut de config.py sont chargées (aucun seuil en dur dans les tests)."""
    settings = load_config(_write_config(tmp_path), env=_full_env())
    assert settings.rythme_delai_min_secondes == 3
    assert settings.rythme_delai_max_secondes == 60
    assert settings.rythme_poids_longueur == 0.6
    assert settings.rythme_longueur_reference == 400
    assert settings.rythme_attente_regroupement_secondes == 3
    assert settings.rythme_max_messages_reponse == 3
    assert settings.rythme_max_longueur_message == 300
    assert settings.rythme_intervalle_segments_secondes == 2


def test_rythme_rejects_min_greater_or_equal_max(tmp_path: Path) -> None:
    """Vérifie la validation de S1 : un délai minimal supérieur ou égal au
    maximal est refusé."""
    config_file = _write_config(
        tmp_path,
        rythme_section="rythme:\n  delai_min_secondes: 60\n  delai_max_secondes: 60",
    )
    with pytest.raises(ConfigError):
        load_config(config_file, env=_full_env())


def test_rythme_rejects_weight_out_of_range(tmp_path: Path) -> None:
    """Vérifie la validation de S1 : un poids de longueur hors [0, 1] est refusé."""
    config_file = _write_config(tmp_path, rythme_section="rythme:\n  poids_longueur: 1.5")
    with pytest.raises(ConfigError):
        load_config(config_file, env=_full_env())


def test_rythme_rejects_negative_burst_wait(tmp_path: Path) -> None:
    """Vérifie la validation de S8 : une attente de regroupement négative est refusée."""
    config_file = _write_config(
        tmp_path, rythme_section="rythme:\n  attente_regroupement_secondes: -1"
    )
    with pytest.raises(ConfigError):
        load_config(config_file, env=_full_env())