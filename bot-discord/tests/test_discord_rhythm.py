"""Tests du rythme et du regroupement côté client (bot/discord_client.py, S1-S3, S8).

Comportement observable vérifié : délai avant l'envoi borné par la config (S1),
indicateur « en train d'écrire » actif pendant tout le délai (S2), réponse
longue découpée en messages courts avec intervalle et robustesse à l'échec
d'envoi (S3), rafales de messages consécutifs regroupées en un seul tour (S8).

Le temps est simulé par un faux sommeil qui enregistre les appels et ne bloque
jamais ; le canal Discord et le LLM sont simulés (fakes.py) — aucun appel
réseau, aucun test n'attend en temps réel.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest  # type: ignore[import-untyped]

from bot.config import Settings
from bot.conversation import ConversationHandler
from bot.db import Database
from bot.discord_client import ConversationalBotClient
from bot.llm import LLMClient

from .fakes import FakeAuthor, FakeChannel, FakeGroqClient, FakeHandler, FakeMessage
from .helpers import instant_sleep, read_message_rows, wait_for_burst_processing

# Réponse longue : 40 phrases de 15 caractères, soit 600 caractères — au-delà
# de rythme_max_longueur_message (300) et sous max_messages_reponse × 300.
LONG_REPLY = "Phrase de test. " * 40


def _message(
    settings: Settings, content: str, channel: FakeChannel
) -> Any:
    """Message de DM de l'utilisateur autorisé, sur le canal simulé donné."""
    return FakeMessage(
        author=FakeAuthor(settings.discord_user_id), content=content, channel=channel
    )


@pytest.mark.asyncio
async def test_burst_grouping_single_llm_call(
    settings: Settings, db: Database, llm: LLMClient, fake_groq_client: FakeGroqClient
) -> None:
    """Vérifie S8 : deux messages consécutifs rapides → un seul appel
    handle_burst avec les deux contenus dans l'ordre, une seule réponse, un
    seul appel LLM, et les deux messages mémorisés en base (M1)."""
    handler = ConversationHandler(settings, db, llm)
    client = ConversationalBotClient(settings, handler, sleep=instant_sleep)
    channel = FakeChannel()
    await client.on_message(_message(settings, "premier message", channel))
    await client.on_message(_message(settings, "deuxième message", channel))
    await wait_for_burst_processing(client)
    assert len(fake_groq_client.calls) == 1
    context = fake_groq_client.calls[0]["messages"][1]["content"]
    assert context.index("premier message") < context.index("deuxième message")
    assert channel.sent == ["réponse simulée"]
    rows = read_message_rows(settings.db_path)
    assert [(row[0], row[1]) for row in rows] == [
        ("utilisateur", "premier message"),
        ("utilisateur", "deuxième message"),
        ("bot", "réponse simulée"),
    ]


@pytest.mark.asyncio
async def test_bursts_separated_by_calm_are_two_rounds(settings: Settings) -> None:
    """Vérifie S8 : deux messages séparés par une attente supérieure au délai de
    regroupement (simulée : la première rafale est entièrement traitée avant le
    second message) donnent deux rafales distinctes — deux appels, deux
    réponses."""
    handler: Any = FakeHandler()
    client = ConversationalBotClient(settings, handler, sleep=instant_sleep)
    channel = FakeChannel()
    await client.on_message(_message(settings, "premier", channel))
    await wait_for_burst_processing(client)
    await client.on_message(_message(settings, "second", channel))
    await wait_for_burst_processing(client)
    assert handler.calls == [
        (settings.discord_user_id, ["premier"]),
        (settings.discord_user_id, ["second"]),
    ]
    assert channel.sent == ["réponse simulée", "réponse simulée"]


@pytest.mark.asyncio
async def test_reply_delay_is_applied_with_typing_indicator(settings: Settings) -> None:
    """Vérifie S1 et S2 : l'envoi est précédé d'un délai dans
    [delai_min_secondes, delai_max_secondes], et l'indicateur « en train
    d'écrire » est actif pendant ce délai — ordre observé : frappe active,
    sommeil, envoi. Le premier sommeil enregistré est l'attente de regroupement
    de S8 (aucune frappe active à ce moment)."""
    delays: list[float] = []
    typing_active: list[bool] = []
    channel = FakeChannel()

    async def recording_sleep(delay: float) -> None:
        delays.append(delay)
        typing_active.append(
            bool(channel.typing_events) and channel.typing_events[-1] == "typing:enter"
        )

    handler: Any = FakeHandler()
    client = ConversationalBotClient(settings, handler, sleep=recording_sleep)
    await client.on_message(_message(settings, "salut, ça va ?", channel))
    await wait_for_burst_processing(client)
    assert delays[0] == settings.rythme_attente_regroupement_secondes
    assert settings.rythme_delai_min_secondes <= delays[1] <= settings.rythme_delai_max_secondes
    assert typing_active[0] is False
    assert typing_active[1] is True
    assert channel.typing_events == ["typing:enter", "typing:exit"]
    assert channel.sent == ["réponse simulée"]


@pytest.mark.asyncio
async def test_long_reply_split_into_segments_with_interval(settings: Settings) -> None:
    """Vérifie S3 : une réponse longue est découpée en 2 ou 3 messages courts
    (chacun ≤ rythme_max_longueur_message), et l'intervalle configuré
    (rythme_intervalle_segments_secondes) sépare les envois."""
    delays: list[float] = []

    async def recording_sleep(delay: float) -> None:
        delays.append(delay)

    handler: Any = FakeHandler(reply=LONG_REPLY)
    client = ConversationalBotClient(settings, handler, sleep=recording_sleep)
    channel = FakeChannel()
    await client.on_message(_message(settings, "salut", channel))
    await wait_for_burst_processing(client)
    assert 2 <= len(channel.sent) <= settings.rythme_max_messages_reponse
    assert all(len(segment) <= settings.rythme_max_longueur_message for segment in channel.sent)
    assert delays[0] == settings.rythme_attente_regroupement_secondes
    interval_calls = [
        delay for delay in delays[1:] if delay == settings.rythme_intervalle_segments_secondes
    ]
    assert len(interval_calls) == len(channel.sent) - 1


@pytest.mark.asyncio
async def test_failed_segment_send_does_not_block_following(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    """Vérifie S3 (robustesse) : l'échec d'envoi d'un segment est logué et ne
    bloque pas l'envoi des segments suivants de la même réponse."""
    channel = FakeChannel(fail_first_sends=1)
    handler: Any = FakeHandler(reply=LONG_REPLY)
    client = ConversationalBotClient(settings, handler, sleep=instant_sleep)
    await client.on_message(_message(settings, "salut", channel))
    with caplog.at_level(logging.ERROR):
        await wait_for_burst_processing(client)
    assert channel.send_attempts >= 2  # tous les segments ont été tentés
    assert 1 <= len(channel.sent) <= settings.rythme_max_messages_reponse - 1
    assert all(len(segment) <= settings.rythme_max_longueur_message for segment in channel.sent)
    assert "Échec de l'envoi d'un segment" in caplog.text


@pytest.mark.asyncio
async def test_none_reply_sends_nothing(settings: Settings) -> None:
    """Vérifie la robustesse : une génération en échec (réponse None) → aucun
    envoi, aucun indicateur de frappe, aucun crash."""
    handler: Any = FakeHandler(reply=None)
    client = ConversationalBotClient(settings, handler, sleep=instant_sleep)
    channel = FakeChannel()
    await client.on_message(_message(settings, "salut", channel))
    await wait_for_burst_processing(client)
    assert channel.sent == []
    assert channel.typing_events == []