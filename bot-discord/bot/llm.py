"""Client API Anthropic : construction du contexte et génération des réponses.

Le prompt système est assemblé depuis deux fichiers fournis par
persona-designer (S4) :
- ``persona.md`` : la personnalité (prénom, caractère, façon de parler) ;
- ``prompts/conversation.md`` : les consignes de conversation (ton oral S5,
  format de sortie).

Lot 1 : la réponse est un texte brut. Lot 3 : le prompt conversation.md
demandera une sortie JSON ``{"reponse": [...], "conversation_finie": bool}``
qu'il faudra parser ici ; la structure actuelle (contexte puis appel unique)
est prévue pour cette évolution.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import anthropic
from anthropic.types import TextBlock

from bot.clock import now
from bot.config import Settings
from bot.db import MemoryMessage

logger = logging.getLogger(__name__)

_JOURS: tuple[str, ...] = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS: tuple[str, ...] = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

# Emplacement prévu par persona-designer dans prompts/conversation.md pour
# l'injection du contenu complet de persona.md.
_PERSONA_PLACEHOLDER = "[INJECTER ICI LE CONTENU COMPLET DU FICHIER persona.md]"


def _assemble_system_prompt(persona: str, conversation_prompt: str) -> str:
    """Compose le prompt système : personnalité injectée au bon endroit (S4).

    Le placeholder défini par persona-designer est remplacé par le contenu de
    persona.md ; s'il est absent (fichier modifié), la personnalité est
    préfixée au prompt de conversation.
    """
    if _PERSONA_PLACEHOLDER in conversation_prompt:
        return conversation_prompt.replace(_PERSONA_PLACEHOLDER, persona)
    return f"{persona}\n\n{conversation_prompt}"


def _read_text_file(path: Path, description: str) -> str:
    """Lit un fichier texte UTF-8 ; lève une erreur claire s'il manque."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Fichier {description} introuvable : {path}. "
            "Il doit être fourni par persona-designer avant de lancer le bot."
        ) from None


def _format_datetime_fr(moment: dt.datetime) -> str:
    """Formate un datetime en français sans dépendre de la locale du système."""
    return (
        f"{_JOURS[moment.weekday()]} {moment.day} {_MOIS[moment.month - 1]} {moment.year}, "
        f"{moment.hour:02d}:{moment.minute:02d}"
    )


def format_recent_messages(messages: list[MemoryMessage], moment: dt.datetime) -> str:
    """Met en forme le bloc de contexte envoyé au LLM : date, heure et messages récents (M1, M4)."""
    lines = [f"Date et heure actuelles : {_format_datetime_fr(moment)}", "", "Conversation récente :"]
    for message in messages:
        lines.append(f"{message.auteur} : {message.contenu}")
    return "\n".join(lines)


class LLMClient:
    """Encapsule le client Anthropic, les prompts et l'appel de génération."""

    def __init__(self, config: Settings, client: anthropic.AsyncAnthropic | None = None) -> None:
        self._config = config
        # Le client HTTP est créé paresseusement pour éviter toute création
        # avant la boucle d'événements ; les tests injectent un faux client.
        self._injected_client = client
        self._persona = _read_text_file(config.persona_path, "persona.md")
        self._conversation_prompt = _read_text_file(config.conversation_prompt_path, "prompts/conversation.md")

    def _get_client(self) -> anthropic.AsyncAnthropic:
        """Renvoie le client Anthropic, en le créant à la première utilisation."""
        if self._injected_client is None:
            self._injected_client = anthropic.AsyncAnthropic(api_key=self._config.anthropic_api_key)
        return self._injected_client

    def system_prompt(self) -> str:
        """Assemble le prompt système : persona injectée dans les consignes (S4, S5)."""
        return _assemble_system_prompt(self._persona, self._conversation_prompt)

    async def generate_reply(
        self,
        recent_messages: list[MemoryMessage],
        moment: dt.datetime | None = None,
    ) -> str | None:
        """Génère la réponse à partir des messages récents de la conversation.

        Renvoie ``None`` si l'API échoue : l'erreur est loguée sans aucune donnée
        sensible (clé API, contenu) et le bot garde le silence plutôt que de
        crasher (exigence de robustesse du lot 1).
        """
        moment = moment if moment is not None else now()
        try:
            response = await self._get_client().messages.create(
                model=self._config.llm_model,
                max_tokens=self._config.llm_max_tokens,
                system=self.system_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": format_recent_messages(recent_messages, moment),
                    }
                ],
            )
        except anthropic.APIError as exc:
            logger.error("Erreur API Anthropic : %s", exc)
            return None
        # Seuls les blocs texte comptent ; les blocs de raisonnement sont ignorés.
        return "".join(block.text for block in response.content if isinstance(block, TextBlock)).strip()