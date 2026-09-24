"""Tests du style S5 sur les exemples de conversation (prompts/exemples-conversation.md).

Test basé sur le fichier d'exemples fourni par persona-designer, pas sur le
vrai LLM : on vérifie que les sorties attendues respectent le ton oral S5
(pas de liste, pas de titre, pas de formule d'assistant, pas d'emoji).
"""

from __future__ import annotations

import re
from pathlib import Path

EXAMPLES_PATH = Path(__file__).resolve().parents[1] / "prompts" / "exemples-conversation.md"

# Formules d'assistant interdites, en minuscules (S5).
_ASSISTANT_PHRASES: tuple[str, ...] = (
    "bien sûr",
    "n'hésite pas",
    "en tant qu'assistant",
    "que puis-je faire",
    "je suis là pour",
    "si tu as besoin",
    "je t'en prie",
    "avec plaisir",
    "pas de problème",
    "je vous en prie",
)

# Plages Unicode des emojis et symboles parasites courants.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002600-\U000027BF"
    "\u2B00-\u2BFF"
    "\uFE0F"
    "\u2764"
    "\U0001F900-\U0001F9FF"
    "]"
)

# Débuts de ligne d'une liste ou d'un titre Markdown.
_LIST_OR_HEADING_RE = re.compile(r"^\s*(#|\s*[-*+]|\s*\d+\.)", re.MULTILINE)


def _expected_outputs() -> list[str]:
    """Extrait les sorties attendues des trois premiers exemples (l'exemple 4 est conditionnel)."""
    text = EXAMPLES_PATH.read_text(encoding="utf-8")
    outputs: list[str] = []
    for raw_section in text.split("## Exemple ")[1:]:
        numero = raw_section.split("—", 1)[0].strip().split(" ")[0]
        if numero == "4":
            continue
        if "Sortie" not in raw_section:
            continue
        tail = raw_section.split("Sortie", 1)[1]
        outputs.extend(re.findall(r"«([^»]*)»", tail))
    return [output.strip() for output in outputs if output.strip()]


def test_expected_outputs_are_read() -> None:
    """Vérifie que le fichier d'exemples est bien lu : 3 exemples plus 1 variante, soit 4 sorties."""
    outputs = _expected_outputs()
    assert len(outputs) == 4
    assert all(outputs)


def test_no_assistant_formulas_in_examples() -> None:
    """Vérifie S5 : aucune formule d'assistant dans les sorties attendues des exemples."""
    for output in _expected_outputs():
        lowered = output.lower()
        for phrase in _ASSISTANT_PHRASES:
            assert phrase not in lowered, (
                f"Formule d'assistant détectée (« {phrase} ») dans : {output}"
            )


def test_no_list_or_heading_in_examples() -> None:
    """Vérifie S5 : les sorties attendues ne contiennent ni liste ni titre Markdown."""
    for output in _expected_outputs():
        assert _LIST_OR_HEADING_RE.search(output) is None, f"Liste ou titre détecté dans : {output}"


def test_no_emoji_in_examples() -> None:
    """Vérifie S5 : les sorties attendues ne contiennent ni emoji ni symbole parasite."""
    for output in _expected_outputs():
        assert _EMOJI_RE.search(output) is None, f"Emoji ou symbole parasite détecté dans : {output}"


def test_emoji_detection_works() -> None:
    """Contrôle positif : la regex anti-emoji détecte bien un émoji Unicode."""
    assert _EMOJI_RE.search("salut \U0001F600") is not None


def test_list_detection_works() -> None:
    """Contrôle positif : la détection de liste et de titre Markdown fonctionne."""
    assert _LIST_OR_HEADING_RE.search("- un item") is not None
    assert _LIST_OR_HEADING_RE.search("# Titre") is not None