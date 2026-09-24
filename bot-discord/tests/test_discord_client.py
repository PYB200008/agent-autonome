"""Tests du filtrage strict du client Discord (bot/discord_client.py, S4 et sécurité).

Les messages sont des objets simulés (fakes.py) : aucun socket, aucun appel
réseau. Le client Discord est instancié dans des tests asyncio, où une boucle
d'événements existe, mais il n'est jamais connecté.
"""

from __future__ import annotations

from typing import Any

import pytest  # type: ignore[import-untyped]

from bot.config import Settings
from bot.conversation import ConversationHandler
from bot.db import Database
from bot.discord_client import ConversationalBotClient
from bot.llm import LLMClient

from .fakes import FakeAuthor, FakeHandler, FakeMessage
from .helpers import read_message_rows

OTHER_USER_ID = 777777777777777777


@pytest.mark.asyncio
async def test_guild_message_is_ignored(settings: Settings) -> None:
    """Vérifie S4 : un message de serveur ne déclenche ni LLM ni envoi."""
    handler: Any = FakeHandler()
    client = ConversationalBotClient(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id), content="salut", guild=object()
    )
    await client.on_message(message)
    assert handler.calls == []
    assert message.channel.sent == []


@pytest.mark.asyncio
async def test_dm_from_other_account_is_ignored(settings: Settings) -> None:
    """Vérifie S4 et le critère d'acceptation : un autre compte ne reçoit aucune réponse."""
    handler: Any = FakeHandler()
    client = ConversationalBotClient(settings, handler)
    message: Any = FakeMessage(author=FakeAuthor(OTHER_USER_ID), content="salut")
    await client.on_message(message)
    assert handler.calls == []
    assert message.channel.sent == []


@pytest.mark.asyncio
async def test_dm_from_bot_itself_is_ignored(settings: Settings) -> None:
    """Vérifie S4 : le bot ignore ses propres messages, même avec l'identifiant autorisé."""
    handler: Any = FakeHandler()
    client = ConversationalBotClient(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id, bot=True), content="réponse du bot"
    )
    await client.on_message(message)
    assert handler.calls == []
    assert message.channel.sent == []


@pytest.mark.asyncio
async def test_dm_authorized_is_processed_and_replied(settings: Settings) -> None:
    """Vérifie S4 : un DM de l'utilisateur autorisé déclenche le traitement puis l'envoi."""
    handler: Any = FakeHandler()
    client = ConversationalBotClient(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id), content="salut, ça va ?"
    )
    await client.on_message(message)
    assert handler.calls == [(settings.discord_user_id, "salut, ça va ?")]
    assert message.channel.sent == ["réponse simulée"]


@pytest.mark.asyncio
async def test_dm_with_blank_content_is_ignored(settings: Settings) -> None:
    """Vérifie S4 (robustesse) : un message sans contenu n'est ni traité ni répondu."""
    handler: Any = FakeHandler()
    client = ConversationalBotClient(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id), content="   "
    )
    await client.on_message(message)
    assert handler.calls == []
    assert message.channel.sent == []


@pytest.mark.asyncio
async def test_dm_authorized_full_flow(settings: Settings, db: Database, llm: LLMClient) -> None:
    """Vérifie S4 et M1 de bout en bout : réponse envoyée et échange mémorisé."""
    handler = ConversationHandler(settings, db, llm)
    client = ConversationalBotClient(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id), content="salut, ça va ?"
    )
    await client.on_message(message)
    assert message.channel.sent == ["réponse simulée"]
    rows = read_message_rows(settings.db_path)
    assert [(row[0], row[1]) for row in rows] == [
        ("utilisateur", "salut, ça va ?"),
        ("bot", "réponse simulée"),
    ]