"""Point d'entrée du bot conversationnel Discord.

Charge les secrets (.env), la configuration (config.yaml), puis lance le
client Discord. Les fichiers de prompts (persona.md, prompts/conversation.md)
doivent exister : le démarrage échoue avec un message clair sinon.
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv

from bot.config import load_config
from bot.conversation import ConversationHandler
from bot.db import Database
from bot.discord_client import ConversationalBotClient
from bot.llm import LLMClient


def main() -> None:
    """Démarre le bot : configuration, base SQLite, LLM, puis boucle Discord."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_dotenv()
    config = load_config()

    db = Database(config.db_path)
    llm = LLMClient(config)
    handler = ConversationHandler(config, db, llm)
    client = ConversationalBotClient(config, handler)
    client.run(config.discord_token)


if __name__ == "__main__":
    main()