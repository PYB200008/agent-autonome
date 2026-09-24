"""Tests du filtrage strict du client Discord (bot/discord_client.py, S4 et sécurité).

Les messages sont des objets simulés (fakes.py) : aucun socket, aucun appel
réseau. Le client Discord est instancié dans des tests asyncio, où une boucle
d'événements existe, mais il n'est jamais connecté.

Depuis le lot 2 (S8), le traitement d'un message autorisé est asynchrone :
``on_message`` n'attend pas la fin de la réponse. Les tests injectent donc un
faux sommeil instantané (helpers.instant_sleep) et attendent la tâche de
traitement (helpers.wait_for_burst_processing) — aucun test n'attend en temps
réel.
"""

from __future__ import annotations

from typing import Any

import discord
import pytest  # type: ignore[import-untyped]

from bot.config import Settings
from bot.conversation import ConversationHandler
from bot.db import Database
from bot.discord_client import ConversationalBotClient
from bot.llm import LLMClient

from .fakes import FakeAuthor, FakeChannel, FakeHandler, FakeMessage
from .helpers import instant_sleep, read_message_rows, wait_for_burst_processing

OTHER_USER_ID = 777777777777777777


def _client(settings: Settings, handler: Any) -> ConversationalBotClient:
    """Client de test avec le faux sommeil instantané (temps simulé, S8)."""
    return ConversationalBotClient(settings, handler, sleep=instant_sleep)


@pytest.mark.asyncio
async def test_guild_message_is_ignored(settings: Settings) -> None:
    """Vérifie S4 : un message de serveur ne déclenche ni LLM ni envoi, et ne
    crée aucune tâche de rafale (S8)."""
    handler: Any = FakeHandler()
    client = _client(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id), content="salut", guild=object()
    )
    await client.on_message(message)
    assert handler.calls == []
    assert message.channel.sent == []
    assert client._burst_task is None
    assert client._pending_contents == []


@pytest.mark.asyncio
async def test_group_dm_is_ignored(settings: Settings) -> None:
    """Vérifie S4 et le périmètre « groupes exclus » : un DM de groupe (channel
    de type ``group``, auteur autorisé, sans serveur) ne déclenche ni appel LLM
    ni envoi, et ne crée aucune tâche de rafale (S8)."""
    handler: Any = FakeHandler()
    client = _client(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id),
        content="salut",
        channel=FakeChannel(discord.ChannelType.group),
    )
    await client.on_message(message)
    assert handler.calls == []
    assert message.channel.sent == []
    assert client._burst_task is None
    assert client._pending_contents == []


@pytest.mark.asyncio
async def test_dm_from_other_account_is_ignored(settings: Settings) -> None:
    """Vérifie S4 et le critère d'acceptation : un autre compte ne reçoit aucune
    réponse, et ne crée aucune tâche de rafale (S8)."""
    handler: Any = FakeHandler()
    client = _client(settings, handler)
    message: Any = FakeMessage(author=FakeAuthor(OTHER_USER_ID), content="salut")
    await client.on_message(message)
    assert handler.calls == []
    assert message.channel.sent == []
    assert client._burst_task is None
    assert client._pending_contents == []


@pytest.mark.asyncio
async def test_dm_from_bot_itself_is_ignored(settings: Settings) -> None:
    """Vérifie S4 : le bot ignore ses propres messages, même avec l'identifiant
    autorisé, et ne crée aucune tâche de rafale (S8)."""
    handler: Any = FakeHandler()
    client = _client(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id, bot=True), content="réponse du bot"
    )
    await client.on_message(message)
    assert handler.calls == []
    assert message.channel.sent == []
    assert client._burst_task is None
    assert client._pending_contents == []


@pytest.mark.asyncio
async def test_dm_authorized_is_processed_and_replied(settings: Settings) -> None:
    """Vérifie S4 et S8 : un DM de l'utilisateur autorisé déclenche le traitement
    de la rafale puis l'envoi. Le traitement étant asynchrone (tâche créée par
    on_message), le test attend sa fin via wait_for_burst_processing, avec le
    faux sommeil instantané (aucun temps réel)."""
    handler: Any = FakeHandler()
    client = _client(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id), content="salut, ça va ?"
    )
    await client.on_message(message)
    await wait_for_burst_processing(client)
    assert handler.calls == [(settings.discord_user_id, ["salut, ça va ?"])]
    assert message.channel.sent == ["réponse simulée"]


@pytest.mark.asyncio
async def test_dm_with_blank_content_is_ignored(settings: Settings) -> None:
    """Vérifie S4 (robustesse) : un message sans contenu n'est ni traité ni
    répondu, et ne crée aucune tâche de rafale (S8)."""
    handler: Any = FakeHandler()
    client = _client(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id), content="   "
    )
    await client.on_message(message)
    assert handler.calls == []
    assert message.channel.sent == []
    assert client._burst_task is None
    assert client._pending_contents == []


@pytest.mark.asyncio
async def test_dm_authorized_full_flow(settings: Settings, db: Database, llm: LLMClient) -> None:
    """Vérifie S4, S8 et M1 de bout en bout : réponse envoyée et échange
    mémorisé. Le traitement étant asynchrone, le test attend la tâche de
    traitement (faux sommeil instantané, aucun temps réel)."""
    handler = ConversationHandler(settings, db, llm)
    client = _client(settings, handler)
    message: Any = FakeMessage(
        author=FakeAuthor(settings.discord_user_id), content="salut, ça va ?"
    )
    await client.on_message(message)
    await wait_for_burst_processing(client)
    assert message.channel.sent == ["réponse simulée"]
    rows = read_message_rows(settings.db_path)
    assert [(row[0], row[1]) for row in rows] == [
        ("utilisateur", "salut, ça va ?"),
        ("bot", "réponse simulée"),
    ]