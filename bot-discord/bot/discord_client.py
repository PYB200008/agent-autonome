"""Client Discord : intents DM, filtrage strict et réponse en DM.

Le bot ne répond qu'aux messages privés de l'utilisateur autorisé
(``DISCORD_USER_ID`` dans .env). Tout message de serveur ou d'un autre compte
est ignoré immédiatement, avant tout autre traitement (S4, sécurité).
"""

from __future__ import annotations

import logging

import discord

from bot.config import Settings
from bot.conversation import ConversationHandler

logger = logging.getLogger(__name__)


class ConversationalBotClient(discord.Client):
    """Client minimal : intents DM + contenu des messages, une seule conversation."""

    def __init__(self, config: Settings, handler: ConversationHandler) -> None:
        # Intents strictement nécessaires : DM et contenu des messages.
        intents = discord.Intents.none()
        intents.dm_messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self._config = config
        self._handler = handler

    async def on_ready(self) -> None:
        """Log sobre de la connexion, sans aucune donnée sensible."""
        logger.info("Connecté à Discord (DM uniquement, utilisateur cible %s)", self._config.discord_user_id)

    async def on_message(self, message: discord.Message) -> None:
        # Filtrage strict : première ligne, ignore tout message hors DM de
        # l'utilisateur autorisé (S4).
        if message.guild is not None or message.author.id != self._config.discord_user_id:
            return
        # Le bot ne répond jamais à ses propres messages.
        if message.author.bot:
            return
        content = message.content.strip()
        if not content:
            return
        try:
            reply = await self._handler.handle_incoming(message.author.id, content)
        except Exception:
            logger.exception("Erreur inattendue dans on_message")
            return
        if reply is None:
            return
        try:
            await message.channel.send(reply)
        except discord.DiscordException:
            logger.exception("Échec de l'envoi de la réponse Discord")