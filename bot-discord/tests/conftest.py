"""Fixtures communes des tests du bot conversationnel (lot 1).

Docstrings en français, identifiants en anglais. Aucun secret réel : les
jetons et clés ci-dessous sont des valeurs factices. Aucun appel réseau :
le client Groq (API OpenAI-compatible) est simulé (fakes.py) et le client
Discord n'est jamais connecté. Les tests des lots suivants se brancheront
sur ces mêmes fixtures.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest  # type: ignore[import-untyped]

# Rend le package `bot` importable quel que soit le répertoire de lancement.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.clock import reset_now
from bot.config import Settings, load_config
from bot.db import Database
from bot.llm import LLMClient

from .fakes import FakeGroqClient


@pytest.fixture(autouse=True)
def restore_clock() -> Iterator[None]:
    """Rétablit l'horloge réelle après chaque test (temps simulé propre)."""
    yield
    reset_now()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Configuration de test : base SQLite temporaire et vrais fichiers de prompts.

    Le chemin de la base pointe vers tmp_path, jamais vers la vraie bot.db du
    projet. Les fichiers persona.md et prompts/conversation.md sont ceux du
    dépôt, pour tester l'injection réelle du prompt (S4).
    """
    project_dir = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "test.db"
    env = {
        "DISCORD_TOKEN": "jeton-de-test-factice",
        "DISCORD_USER_ID": "424242424242424242",
        "GROQ_API_KEY": "cle-de-test-factice",
    }
    config_yaml = "\n".join(
        [
            "memoire:",
            "  court_terme_max_messages: 30",
            "llm:",
            "  model: modele-de-test",
            "  max_tokens: 128",
            "db:",
            f"  path: '{db_path.as_posix()}'",
            "prompts:",
            f"  persona_path: '{(project_dir / 'persona.md').as_posix()}'",
            f"  conversation_path: '{(project_dir / 'prompts' / 'conversation.md').as_posix()}'",
        ]
    )
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_yaml, encoding="utf-8")
    return load_config(config_file, env=env)


@pytest.fixture
def db(settings: Settings) -> Iterator[Database]:
    """Base SQLite temporaire du test, fermée proprement en fin de test."""
    database = Database(settings.db_path)
    yield database
    database.close()


@pytest.fixture
def fake_groq_client() -> FakeGroqClient:
    """Faux client Groq (API OpenAI-compatible) : aucune requête réseau pendant les tests."""
    return FakeGroqClient()


@pytest.fixture
def llm(settings: Settings, fake_groq_client: FakeGroqClient) -> LLMClient:
    """Client LLM branché sur le faux client HTTP Groq (aucun appel réseau)."""
    return LLMClient(settings, client=cast(Any, fake_groq_client))