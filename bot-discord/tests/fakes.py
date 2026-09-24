"""Objets simulés pour les tests (lot 1).

Aucun objet réel n'est instancié : ni socket discord.py, ni requête HTTP
Anthropic. Ces fakes pilotent uniquement les branches du code testé, sans
aucun accès au réseau.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import discord
from anthropic.types import TextBlock


class FakeAnthropicClient:
    """Simule anthropic.AsyncAnthropic : réponse en texte, aucun réseau."""

    def __init__(self, reply: str = "réponse simulée") -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []
        self.error: BaseException | None = None
        self.blocks: list[Any] | None = None
        self._messages = _FakeMessages(self)

    @property
    def messages(self) -> _FakeMessages:
        """Point d'entrée messages simulé de l'API Anthropic."""
        return self._messages


class _FakeMessages:
    """Simule le point d'entrée messages du client Anthropic."""

    def __init__(self, client: FakeAnthropicClient) -> None:
        self._client = client

    async def create(self, **kwargs: Any) -> Any:
        """Enregistre l'appel et renvoie les blocs simulés."""
        if self._client.error is not None:
            raise self._client.error
        self._client.calls.append(dict(kwargs))
        if self._client.blocks is not None:
            return SimpleNamespace(content=self._client.blocks)
        return SimpleNamespace(content=[TextBlock(type="text", text=self._client.reply)])


class FakeAuthor:
    """Auteur de message Discord simulé (identifiant numérique et drapeau bot)."""

    def __init__(self, author_id: int, bot: bool = False) -> None:
        self.id = author_id
        self.bot = bot


class FakeChannel:
    """Canal de DM simulé : enregistre les envois sans réseau.

    L'attribut ``type`` reproduit ``discord.ChannelType`` pour le filtrage
    du client (DM privé accepté, DM de groupe exclu).
    """

    def __init__(
        self, channel_type: discord.ChannelType = discord.ChannelType.private
    ) -> None:
        self.type = channel_type
        self.sent: list[str] = []

    async def send(self, content: str) -> None:
        """Simule l'envoi d'un message sur le canal."""
        self.sent.append(content)


class FakeMessage:
    """Message Discord simulé, minimal pour les branches testées."""

    def __init__(
        self,
        author: FakeAuthor,
        content: str = "",
        guild: Any = None,
        channel: FakeChannel | None = None,
    ) -> None:
        self.author = author
        self.content = content
        self.guild = guild
        self.channel = channel if channel is not None else FakeChannel()


class FakeHandler:
    """Gestionnaire de conversation simulé : enregistre les appels entrants."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    async def handle_incoming(self, user_id: int, content: str) -> str:
        """Simule le traitement d'un message entrant et renvoie une réponse."""
        self.calls.append((user_id, content))
        return "réponse simulée"