"""Gestion d'une conversation (lot 1) : mémorisation court terme puis réponse.

Ce module orchestre le flux d'un message entrant :
1. enregistrement du message en base ;
2. relecture des derniers messages (M1) ;
3. génération de la réponse par le LLM ;
4. mémorisation de la réponse.

Les lots suivants enrichiront ce flux (états C, rythme S, relances R).
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

    async def handle_incoming(self, user_id: int, content: str) -> str | None:
        """Traite un message de l'utilisateur et renvoie le texte à envoyer.

        Le message est enregistré, puis les ``court_terme_max_messages`` derniers
        messages sont relus et injectés dans le contexte du LLM (M1). La réponse
        est elle aussi mémorisée.

        Renvoie ``None`` en cas d'erreur de génération (déjà loguée ici ou dans
        le module LLM) : le bot garde le silence et ne crashe pas.
        """
        try:
            conversation_id = self._db.get_or_create_conversation(str(user_id))
            self._db.insert_message(conversation_id, AUTEUR_UTILISATEUR, content)
            recent = self._db.recent_messages(conversation_id, self._config.memory_max_messages)
            reply = await self._llm.generate_reply(recent)
            if reply is None:
                return None
            self._db.insert_message(conversation_id, AUTEUR_BOT, reply)
            return reply
        except Exception:
            logger.exception("Erreur pendant le traitement d'un message entrant")
            return None