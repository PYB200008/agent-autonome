"""Gestion d'une conversation (lots 1 et 2) : mémorisation puis réponse.

Ce module orchestre le flux d'un message entrant :
1. enregistrement du message en base ;
2. relecture des derniers messages (M1) ;
3. génération de la réponse par le LLM ;
4. mémorisation de la réponse.

Lot 2 (S8) : une rafale de messages consécutifs est traitée comme un seul
tour via ``handle_burst`` — tous les messages sont mémorisés, un seul appel
LLM, une seule réponse. ``handle_incoming`` (lot 1) reste disponible pour un
message isolé ; il revient au même chemin avec une rafale d'un seul élément.
Le découpage de la réponse en plusieurs messages (S3) se fait côté envoi,
sans changer la mémoire : le texte complet de la réponse est mémorisé.
"""

from __future__ import annotations

import logging

from bot.config import Settings
from bot.db import Database
from bot.llm import LLMClient

logger = logging.getLogger(__name__)

# Rôles stockés dans la table messages.
AUTEUR_UTILISATEUR = "utilisateur"
AUTEUR_BOT = "bot"


class ConversationHandler:
    """Enchaîne la mémorisation (M1) et la génération de réponse."""

    def __init__(self, config: Settings, db: Database, llm: LLMClient) -> None:
        self._config = config
        self._db = db
        self._llm = llm

    async def handle_burst(self, user_id: int, contents: list[str]) -> str | None:
        """Traite une rafale de messages comme un seul tour (S8, M1).

        Tous les messages de la rafale sont enregistrés, puis les
        ``court_terme_max_messages`` derniers messages sont relus et injectés
        dans le contexte du LLM (un seul appel pour l'ensemble, S8). La
        réponse est mémorisée telle quelle.

        Renvoie ``None`` en cas d'erreur de génération (déjà loguée ici ou
        dans le module LLM) : le bot garde le silence et ne crashe pas.
        """
        try:
            conversation_id = self._db.get_or_create_conversation(str(user_id))
            for content in contents:
                self._db.insert_message(conversation_id, AUTEUR_UTILISATEUR, content)
            recent = self._db.recent_messages(conversation_id, self._config.memory_max_messages)
            reply = await self._llm.generate_reply(recent)
            if not reply:
                return None
            self._db.insert_message(conversation_id, AUTEUR_BOT, reply)
            return reply
        except Exception:
            logger.exception("Erreur pendant le traitement d'un message entrant")
            return None

    async def handle_incoming(self, user_id: int, content: str) -> str | None:
        """Traite un message isolé (interface conservée depuis le lot 1).

        Équivaut à une rafale d'un seul message : mémorisation, contexte (M1),
        génération LLM, mémorisation de la réponse. Renvoie ``None`` en cas
        d'erreur de génération (silence).
        """
        return await self.handle_burst(user_id, [content])