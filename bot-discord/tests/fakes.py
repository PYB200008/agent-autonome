"""Objets simulés pour les tests (lot 1).

Aucun objet réel n'est instancié : ni socket discord.py, ni requête HTTP vers
Groq. Ces fakes pilotent uniquement les branches du code testé, sans aucun
accès au réseau.

Note de migration (décision utilisateur) : le client simulé reproduit la
forme ``chat.completions.create`` du SDK OpenAI (API OpenAI-compatible de
Groq). Le nom de classe historique ``FakeAnthropicClient`` est conservé pour
ne pas casser les imports existants ; le renommer en ``FakeGroqClient`` fera
partie de l'adaptation des tests par le tester.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import discord


class FakeAnthropicClient:
    """Simule un client OpenAI-compatible (Groq) : réponse en texte, aucun réseau."""

    def __init__(self, reply: str = "réponse simulée") -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []
        self.error: BaseException | None = None
        self._chat = _FakeChat(self)

    @property
    def chat(self) -> _FakeChat:
        """Point d'entrée chat du client simulé."""
        return self._chat


class _FakeChat:
    """Simule le sous-client ``chat`` du client OpenAI-compatible."""

    def __init__(self, client: FakeAnthropicClient) -> None:
        self._client = client
        self.completions = _FakeCompletions(client)


class _FakeCompletions:
    """Simule ``chat.completions.create`` (format OpenAI-compatible de Groq)."""

    def __init__(self, client: FakeAnthropicClient) -> None:
        self._client = client

    async def create(self, **kwargs: Any) -> Any:
        """Enregistre l'appel et renvoie une complétion simulée."""
        if self._client.error is not None:
            raise self._client.error
        self._client.calls.append(dict(kwargs))
        message = SimpleNamespace(content=self._client.reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


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