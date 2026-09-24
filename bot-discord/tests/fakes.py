"""Objets simulés pour les tests (lots 1 et 2).

Aucun objet réel n'est instancié : ni socket discord.py, ni requête HTTP vers
Groq. Ces fakes pilotent uniquement les branches du code testé, sans aucun
accès au réseau.

Lot 2 : FakeHandler traite les rafales entières (S8), FakeChannel simule
l'indicateur « en train d'écrire » (S2) et peut échouer à l'envoi d'un message
(robustesse de S3).

Note de migration (décision utilisateur) : le client simulé reproduit la
forme ``chat.completions.create`` du SDK OpenAI (API OpenAI-compatible de
Groq). La classe porte le nom ``FakeGroqClient`` depuis l'adaptation des
tests à la bascule Anthropic → Groq ; l'ancien nom ``FakeAnthropicClient``
n'existe plus.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import discord


class FakeGroqClient:
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

    def __init__(self, client: FakeGroqClient) -> None:
        self._client = client
        self.completions = _FakeCompletions(client)


class _FakeCompletions:
    """Simule ``chat.completions.create`` (format OpenAI-compatible de Groq)."""

    def __init__(self, client: FakeGroqClient) -> None:
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
    """Canal de DM simulé : enregistre les envois et la frappe simulée sans réseau.

    ``typing()`` renvoie un context manager asynchrone (S2) qui enregistre les
    activations dans ``typing_events``. Avec ``fail_first_sends=N``, les N
    premiers envois lèvent une ``discord.DiscordException`` puis réussissent ;
    avec ``fail_sends=True``, tous les envois échouent (robustesse de S3).
    """

    def __init__(
        self,
        channel_type: discord.ChannelType = discord.ChannelType.private,
        *,
        fail_sends: bool = False,
        fail_first_sends: int = 0,
    ) -> None:
        self.type = channel_type
        self.sent: list[str] = []
        self.send_attempts: int = 0
        self.typing_events: list[str] = []
        self._fail_sends = fail_sends
        self._fail_first_sends = fail_first_sends

    async def send(self, content: str) -> None:
        """Simule l'envoi d'un message ; lève DiscordException pendant les échecs configurés."""
        self.send_attempts += 1
        if self._fail_sends or (
            self._fail_first_sends and self.send_attempts <= self._fail_first_sends
        ):
            raise discord.DiscordException("échec d'envoi simulé (S3)")
        self.sent.append(content)

    def typing(self) -> "FakeTyping":
        """Renvoie l'indicateur « en train d'écrire » simulé (S2), sans réseau."""
        return FakeTyping(self)


class FakeTyping:
    """Simule ``channel.typing()`` : enregistre l'activation sans réseau (S2)."""

    def __init__(self, channel: FakeChannel) -> None:
        self._channel = channel

    async def __aenter__(self) -> "FakeTyping":
        self._channel.typing_events.append("typing:enter")
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        self._channel.typing_events.append("typing:exit")


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
    """Gestionnaire de conversation simulé : enregistre les appels de rafales (S8)."""

    def __init__(self, reply: str | None = "réponse simulée") -> None:
        self.calls: list[tuple[int, list[str]]] = []
        self.reply = reply

    async def handle_burst(self, user_id: int, contents: list[str]) -> str | None:
        """Simule le traitement d'une rafale entière et renvoie la réponse configurée.

        ``contents`` est copié pour figer l'ordre et l'état au moment de l'appel.
        Renvoie ``None`` pour simuler un échec de génération (silence du bot).
        """
        self.calls.append((user_id, list(contents)))
        return self.reply