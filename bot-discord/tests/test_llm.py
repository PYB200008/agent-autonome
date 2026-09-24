"""Tests du client LLM (bot/llm.py) : prompt S4, contexte daté M1, robustesse.

Le client HTTP Groq (API OpenAI-compatible) est remplacé par un faux objet :
aucun appel réseau. Le temps est simulé pour vérifier que le contexte envoyé
au LLM est daté. Depuis la bascule Anthropic → Groq (décision utilisateur,
commit dd95f49), ``messages[0]`` est le prompt système et le contexte daté
se trouve dans ``messages[1]``.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, cast

import openai
import pytest  # type: ignore[import-untyped]

from bot.clock import set_now
from bot.config import Settings
from bot.db import MemoryMessage
from bot.llm import LLMClient

from .fakes import FakeGroqClient

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
    fake_groq_client: FakeGroqClient,
    llm: LLMClient,
) -> None:
    """Vérifie M1 : le contexte envoyé au LLM est daté (heure simulée) et contient les récents.

    Depuis la bascule Groq, ``messages[0]`` est le prompt système (role system,
    persona injectée) et ``messages[1]`` le contexte utilisateur daté.
    """
    set_now(lambda: SIMULATED_TIME)
    await llm.generate_reply(SAMPLE_MESSAGES)
    payload = fake_groq_client.calls[-1]
    system_message = payload["messages"][0]
    assert system_message["role"] == "system"
    assert "## L'interlocuteur" in system_message["content"]
    user_message = payload["messages"][1]
    assert user_message["role"] == "user"
    context = user_message["content"]
    assert "Date et heure actuelles :" in context
    assert "14 mars 2026" in context
    assert "09:05" in context
    assert "utilisateur : salut, ça va ?" in context


@pytest.mark.asyncio
async def test_generate_reply_uses_model_from_config(
    settings: Settings,
    fake_groq_client: FakeGroqClient,
    llm: LLMClient,
) -> None:
    """Vérifie R8 : le modèle et max_tokens de la requête Groq viennent de config.yaml, pas du code."""
    await llm.generate_reply(SAMPLE_MESSAGES)
    payload = fake_groq_client.calls[-1]
    assert payload["model"] == settings.llm_model
    assert payload["max_tokens"] == settings.llm_max_tokens


def test_get_client_uses_base_url_and_key_from_config(
    settings: Settings,
    fake_groq_client: FakeGroqClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie R8 : le client Groq est construit avec la clé GROQ_API_KEY et le base_url
    de config.yaml, sans instancier le vrai SDK ni faire d'appel réseau."""
    captured: dict[str, Any] = {}

    def fake_factory(**kwargs: Any) -> FakeGroqClient:
        captured.update(kwargs)
        return fake_groq_client

    monkeypatch.setattr(openai, "AsyncOpenAI", fake_factory)
    llm = LLMClient(settings)
    client = llm._get_client()
    assert client is fake_groq_client
    assert captured["api_key"] == settings.groq_api_key
    assert captured["base_url"] == settings.llm_base_url


@pytest.mark.asyncio
async def test_generate_reply_strips_and_returns_text_content(
    fake_groq_client: FakeGroqClient,
    llm: LLMClient,
) -> None:
    """Vérifie la robustesse : seule la réponse textuelle (choices[0].message.content)
    est renvoyée, débarrassée de ses espaces. Depuis la bascule Groq, le format
    OpenAI n'a pas de blocs de texte à filtrer (l'ancien test des blocs Anthropic
    est remplacé par cette vérification du contenu texte)."""
    fake_groq_client.reply = "  coucou  "
    result = await llm.generate_reply(SAMPLE_MESSAGES)
    assert result == "coucou"


@pytest.mark.asyncio
async def test_generate_reply_logs_api_error_and_returns_none(
    fake_groq_client: FakeGroqClient,
    llm: LLMClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Vérifie la robustesse : une erreur API est loguée et generate_reply renvoie None."""
    fake_groq_client.error = openai.APIError(
        "panne simulée", request=cast(Any, object()), body=None
    )
    with caplog.at_level(logging.ERROR):
        result = await llm.generate_reply(SAMPLE_MESSAGES)
    assert result is None
    assert "Erreur API Groq" in caplog.text


@pytest.mark.asyncio
async def test_generate_reply_never_logs_api_key(
    settings: Settings,
    fake_groq_client: FakeGroqClient,
    llm: LLMClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Vérifie la sécurité : la clé GROQ_API_KEY n'apparaît jamais dans les logs
    lors d'une erreur API."""
    fake_groq_client.error = openai.APIError(
        "panne simulée", request=cast(Any, object()), body=None
    )
    with caplog.at_level(logging.ERROR):
        result = await llm.generate_reply(SAMPLE_MESSAGES)
    assert result is None
    assert settings.groq_api_key not in caplog.text