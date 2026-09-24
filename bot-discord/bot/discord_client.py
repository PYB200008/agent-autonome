"""Client Discord : intents DM, filtrage strict, rythme de réponse (lot 2).

Le bot ne répond qu'aux messages privés (DM) de l'utilisateur autorisé
(``DISCORD_USER_ID`` dans .env). Tout message de serveur, de DM de groupe ou
d'un autre compte est ignoré immédiatement, avant tout autre traitement
(S4, sécurité, périmètre « groupes exclus » du cahier des charges).

Rythme de réponse (lot 2) :
- S8 (regroupement) : les messages consécutifs de l'utilisateur sont mis en
  attente ; un compte à rebours annulable démarre à chaque message et son
  expiration déclenche le traitement de toute la rafale d'un seul coup (une
  seule mémorisation, un seul appel LLM, une seule séquence de réponse) ;
- S1 (délai) : le délai avant l'envoi est variable, proportionnel aux
  longueurs du message reçu et de la réponse, avec une part aléatoire ;
- S2 (indicateur de frappe) : Discord affiche « en train d'écrire » pendant
  tout le délai ;
- S3 (découpage) : la réponse est envoyée en 1 à 3 messages courts, avec un
  petit intervalle entre eux ; l'échec d'un envoi ne bloque pas les suivants.

Le sommeil et le hasard sont injectables (``sleep``, ``rng``) pour que les
tests s'exécutent en temps simulé et de façon reproductible.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

import discord

from bot.config import Settings
from bot.conversation import ConversationHandler
from bot.rhythm import compute_reply_delay, split_reply

logger = logging.getLogger(__name__)

# Fonction de sommeil injectable : dans les tests, un faux qui ne bloque pas.
SleepFunc = Callable[[float], Awaitable[None]]


class ConversationalBotClient(discord.Client):
    """Client Discord : intents DM, filtrage strict, regroupement et rythme (lot 2)."""

    def __init__(
        self,
        config: Settings,
        handler: ConversationHandler,
        *,
        rng: random.Random | None = None,
        sleep: SleepFunc | None = None,
    ) -> None:
        # Intents strictement nécessaires : DM et contenu des messages.
        intents = discord.Intents.none()
        intents.dm_messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self._config = config
        self._handler = handler
        self._rng = rng if rng is not None else random.Random()
        self._sleep: SleepFunc = sleep if sleep is not None else asyncio.sleep
        # État du regroupement de rafales (S8). ``_burst_task`` n'existe que
        # pendant l'attente de fin de rafale ; le traitement démarre ensuite
        # dans ``_processing_task``, qui n'est jamais annulée par un nouveau
        # message : une séquence de réponse en cours va jusqu'au bout.
        self._pending_contents: list[str] = []
        self._burst_channel: discord.abc.Messageable | None = None
        self._burst_task: asyncio.Task[None] | None = None
        self._processing_task: asyncio.Task[None] | None = None
        self._response_lock = asyncio.Lock()

    async def on_ready(self) -> None:
        """Log sobre de la connexion, sans aucune donnée sensible."""
        logger.info("Connecté à Discord (DM uniquement, utilisateur cible %s)", self._config.discord_user_id)

    async def on_message(self, message: discord.Message) -> None:
        # Filtrage strict : première ligne, ignore tout message hors DM privé
        # de l'utilisateur autorisé (S4, périmètre « groupes exclus »).
        if (
            message.guild is not None
            or message.channel.type != discord.ChannelType.private
            or message.author.id != self._config.discord_user_id
        ):
            return
        # Le bot ne répond jamais à ses propres messages.
        if message.author.bot:
            return
        content = message.content.strip()
        if not content:
            return
        # S8 : le message rejoint la rafale en attente ; le compte à rebours
        # en cours est annulé puis relancé (nouvelle échéance après le dernier
        # message reçu).
        self._pending_contents.append(content)
        self._burst_channel = message.channel
        if self._burst_task is not None and not self._burst_task.done():
            self._burst_task.cancel()
        self._burst_task = asyncio.create_task(self._wait_burst_end())

    async def _wait_burst_end(self) -> None:
        """Attend la fin supposée de la rafale, puis lance le traitement (S8).

        Annulée par ``on_message`` si un nouveau message arrive avant
        l'échéance. Le traitement démarre dans une tâche distincte : seule
        l'attente de regroupement est annulable, jamais une séquence de
        réponse déjà en cours.
        """
        try:
            await self._sleep(self._config.rythme_attente_regroupement_secondes)
        except asyncio.CancelledError:
            return
        self._burst_task = None
        self._processing_task = asyncio.create_task(self._process_burst())

    async def _process_burst(self) -> None:
        """Traite toute la rafale : un seul appel LLM, une seule réponse (S8).

        Plusieurs rafales rapprochées sont sérialisées par un verrou : si un
        message arrive pendant le traitement, il attend la fin de la réponse
        en cours, puis est traité à son tour.
        """
        async with self._response_lock:
            contents, self._pending_contents = self._pending_contents, []
            channel = self._burst_channel
            self._burst_channel = None
            if not contents or channel is None:
                return
            try:
                reply = await self._handler.handle_burst(
                    self._config.discord_user_id, contents
                )
            except Exception:
                logger.exception("Erreur inattendue pendant le traitement d'une rafale")
                return
            if reply is None:
                return  # silence : erreur de génération déjà loguée (lot 1)
            try:
                await self._apply_rhythm_and_send(channel, contents, reply)
            except Exception:
                logger.exception("Erreur inattendue pendant l'envoi de la réponse")

    async def _apply_rhythm_and_send(
        self,
        channel: discord.abc.Messageable,
        contents: list[str],
        reply: str,
    ) -> None:
        """Applique le délai (S1), l'indicateur de frappe (S2) puis l'envoi (S3)."""
        input_len = sum(len(content) for content in contents)
        delay = compute_reply_delay(
            input_len=input_len,
            output_len=len(reply),
            min_delay=self._config.rythme_delai_min_secondes,
            max_delay=self._config.rythme_delai_max_secondes,
            length_weight=self._config.rythme_poids_longueur,
            reference_length=self._config.rythme_longueur_reference,
            rng=self._rng,
        )
        # S2 : l'indicateur « en train d'écrire » reste affiché pendant tout
        # le délai de S1 (discord.py relance la frappe automatiquement si le
        # délai dépasse quelques secondes).
        if delay > 0:
            async with channel.typing():
                await self._sleep(delay)
        segments = split_reply(
            reply,
            max_segments=self._config.rythme_max_messages_reponse,
            max_chars_per_segment=self._config.rythme_max_longueur_message,
            rng=self._rng,
        )
        for index, segment in enumerate(segments):
            try:
                await channel.send(segment)
            except discord.DiscordException:
                logger.exception("Échec de l'envoi d'un segment de réponse Discord")
            if index < len(segments) - 1:
                await self._sleep(self._config.rythme_intervalle_segments_secondes)

    async def close(self) -> None:
        """Ferme le client en annulant proprement les tâches en attente."""
        for task in (self._burst_task, self._processing_task):
            if task is not None and not task.done():
                task.cancel()
        await super().close()