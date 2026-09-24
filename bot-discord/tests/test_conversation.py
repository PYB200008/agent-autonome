"""Tests du flux de conversation (bot/conversation.py, M1 et robustesse).

Le LLM est simulé : aucun appel réseau. Le temps est simulé pour vérifier le
contexte daté transmis au LLM.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, cast

import anthropic
import pytest  # type: ignore[import-untyped]

from bot.clock import set_now
from bot.config import Settings
from bot.conversation import ConversationHandler
from bot.db import Database
from bot.llm import LLMClient

from .fakes import FakeAnthropicClient
from .helpers import read_message_rows

USER_ID = 424242424242424242
USER_ID_STR = "424242424242424242"
SIMULATED_TIME = dt.datetime(2026, 3, 14, 9, 5, tzinfo=dt.timezone.utc)


@pytest.mark.asyncio
async def test_handle_incoming_stores_user_then_bot(
    settings: Settings, db: Database, llm: LLMClient
) -> None:
    """Vérifie M1 : le message entrant puis la réponse sont mémorisés avec les bons rôles."""
    handler = ConversationHandler(settings, db, llm)
    reply = await handler.handle_incoming(USER_ID, "salut, ça va ?")
    assert reply == "réponse simulée"
    rows = read_message_rows(settings.db_path)
    assert [(row[0], row[1]) for row in rows] == [
        ("utilisateur", "salut, ça va ?"),
        ("bot", "réponse simulée"),
    ]


@pytest.mark.asyncio
async def test_handle_incoming_context_limited_to_thirty(
    settings: Settings,
    db: Database,
    fake_anthropic_client: FakeAnthropicClient,
    llm: LLMClient,
) -> None:
    """Vérifie M1 : le contexte envoyé au LLM contient les 30 derniers messages, datés, dans l'ordre."""
    set_now(lambda: SIMULATED_TIME)
    conversation_id = db.get_or_create_conversation(USER_ID_STR)
    for i in range(1, 36):
        auteur = "utilisateur" if i % 2 == 1 else "bot"
        db.insert_message(conversation_id, auteur, f"message-{i:02d}")
    handler = ConversationHandler(settings, db, llm)
    await handler.handle_incoming(USER_ID, "dernier message")
    context = fake_anthropic_client.calls[-1]["messages"][0]["content"]
    assert "message-01" not in context
    assert "message-07" in context
    assert "dernier message" in context
    assert "Date et heure actuelles :" in context
    assert "14 mars 2026" in context
    assert context.index("message-07") < context.index("message-09") < context.index("dernier message")


@pytest.mark.asyncio
async def test_handle_incoming_returns_none_on_api_error(
    settings: Settings,
    db: Database,
    fake_anthropic_client: FakeAnthropicClient,
    llm: LLMClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Vérifie la robustesse : erreur LLM loguée, aucun message bot inséré, pas de crash."""
    fake_anthropic_client.error = anthropic.APIError(
        "panne simulée", request=cast(Any, object()), body=None
    )
    handler = ConversationHandler(settings, db, llm)
    with caplog.at_level(logging.ERROR):
        reply = await handler.handle_incoming(USER_ID, "salut")
    assert reply is None
    rows = read_message_rows(settings.db_path)
    assert [row[0] for row in rows] == ["utilisateur"]
    assert "Erreur API Anthropic" in caplog.text


@pytest.mark.asyncio
async def test_handle_incoming_survives_unexpected_error(
    settings: Settings, db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    """Vérifie la robustesse : une exception inattendue est loguée, le bot garde le silence."""

    class BrokenLLM:
        """LLM simulé qui lève une exception inattendue."""

        async def generate_reply(self, recent_messages: Any, moment: Any = None) -> str:
            raise RuntimeError("panne inattendue")

    handler = ConversationHandler(settings, db, cast(Any, BrokenLLM()))
    with caplog.at_level(logging.ERROR):
        reply = await handler.handle_incoming(USER_ID, "salut")
    assert reply is None
    rows = read_message_rows(settings.db_path)
    assert [row[0] for row in rows] == ["utilisateur"]
    assert "Erreur pendant le traitement" in caplog.text