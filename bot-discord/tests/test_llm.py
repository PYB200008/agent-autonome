"""Tests du client LLM (bot/llm.py) : prompt S4, contexte daté M1, robustesse.

Le client HTTP Anthropic est remplacé par un faux objet : aucun appel réseau.
Le temps est simulé pour vérifier que le contexte envoyé au LLM est daté.
"""

from __future__ import annotations

import datetime as dt
import logging
from types import SimpleNamespace
from typing import Any, cast

import anthropic
import pytest  # type: ignore[import-untyped]
from anthropic.types import TextBlock

from bot.clock import set_now
from bot.config import Settings
from bot.db import MemoryMessage
from bot.llm import LLMClient

from .fakes import FakeAnthropicClient

SAMPLE_MESSAGES = [
    MemoryMessage(
        auteur="utilisateur",
        contenu="salut, ça va ?",
        horodatage="2026-03-14T09:05:00+00:00",
    )
]

SIMULATED_TIME = dt.datetime(2026, 3, 14, 9, 5, tzinfo=dt.timezone.utc)


def test_system_prompt_injects_full_persona(settings: Settings) -> None:
    """Vérifie S4 : le prompt système contient le contenu de persona.md injecté, sans placeholder."""
    llm = LLMClient(settings)
    prompt = llm.system_prompt()
    assert "## L'interlocuteur" in prompt
    assert "## Tics de langage" in prompt
    assert "Tu écris en français, à l'oral" in prompt
    assert "scotobi" in prompt
    assert "[INJECTER ICI LE CONTENU COMPLET DU FICHIER persona.md]" not in prompt


@pytest.mark.asyncio
async def test_generate_reply_sends_dated_context(
    settings: Settings,
    fake_anthropic_client: FakeAnthropicClient,
    llm: LLMClient,
) -> None:
    """Vérifie M1 : le contexte envoyé au LLM est daté (heure simulée) et contient les récents."""
    set_now(lambda: SIMULATED_TIME)
    await llm.generate_reply(SAMPLE_MESSAGES)
    payload = fake_anthropic_client.calls[-1]
    assert payload["model"] == settings.llm_model
    context = payload["messages"][0]["content"]
    assert "Date et heure actuelles :" in context
    assert "14 mars 2026" in context
    assert "09:05" in context
    assert "utilisateur : salut, ça va ?" in context


@pytest.mark.asyncio
async def test_generate_reply_keeps_only_text_blocks(
    fake_anthropic_client: FakeAnthropicClient,
    llm: LLMClient,
) -> None:
    """Vérifie la robustesse : seuls les blocs texte de la réponse API sont conservés."""
    fake_anthropic_client.blocks = [
        TextBlock(type="text", text="coucou"),
        SimpleNamespace(text="bloc de raisonnement à ignorer"),
    ]
    result = await llm.generate_reply(SAMPLE_MESSAGES)
    assert result == "coucou"


@pytest.mark.asyncio
async def test_generate_reply_logs_api_error_and_returns_none(
    fake_anthropic_client: FakeAnthropicClient,
    llm: LLMClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Vérifie la robustesse : une erreur API est loguée et generate_reply renvoie None."""
    fake_anthropic_client.error = anthropic.APIError(
        "panne simulée", request=cast(Any, object()), body=None
    )
    with caplog.at_level(logging.ERROR):
        result = await llm.generate_reply(SAMPLE_MESSAGES)
    assert result is None
    assert "Erreur API Anthropic" in caplog.text