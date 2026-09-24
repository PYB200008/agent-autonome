"""Rythme de réponse (lot 2) : délais et découpage de la réponse en messages courts.

Deux fonctions pures, entièrement testables en temps simulé :

- ``compute_reply_delay`` (S1) : délai d'attente avant l'envoi d'une réponse,
  borné dans ``[delai_min_secondes, delai_max_secondes]`` de ``config.yaml``,
  proportionnel aux longueurs du message reçu et de la réponse, avec une part
  aléatoire ;
- ``split_reply`` (S3) : découpe la réponse du LLM en 1 à
  ``max_messages_reponse`` messages courts, de préférence aux fins de phrases,
  sans couper un mot au milieu.

La génération aléatoire est injectable (``random.Random``) afin que les tests
soient reproductibles : les appels de production passent un générateur créé
par le client Discord.
"""

from __future__ import annotations

import math
import random
import re

# Fin de phrase : ponctuation forte (., !, ?, …) ou retour à la ligne. La
# ponctuation reste attachée à la phrase qui la précède ; les blancs suivants
# (espaces, sauts de ligne) servent de séparateur.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+|(?<=\n)\s*")


def compute_reply_delay(
    input_len: int,
    output_len: int,
    min_delay: float,
    max_delay: float,
    length_weight: float,
    reference_length: int,
    rng: random.Random | None = None,
) -> float:
    """Calcule le délai d'attente avant l'envoi de la réponse (S1).

    Formule documentée :

        ratio = min(1.0, (input_len + output_len) / reference_length)
        fraction = length_weight * ratio + (1.0 - length_weight) * hasard
        délai = min_delay + (max_delay - min_delay) * fraction

    ``ratio`` normalise les longueurs cumulées (message reçu + réponse) : 0
    pour un échange très court, 1 à partir de ``reference_length`` caractères.
    ``hasard`` est un tirage uniforme dans [0, 1). Le délai est borné dans
    [min_delay, max_delay].

    Avec les valeurs par défaut de ``config.yaml`` (3 s · 60 s, poids 0.6,
    référence 400), un échange court répond en quelques secondes, un échange
    long tire vers la minute, et la part aléatoire (40 %) évite un rythme
    mécanique.
    """
    if input_len < 0 or output_len < 0:
        raise ValueError("input_len et output_len doivent être positifs ou nuls")
    roll = rng.random() if rng is not None else random.random()
    ratio = min(1.0, (input_len + output_len) / reference_length)
    fraction = length_weight * ratio + (1.0 - length_weight) * roll
    delay = min_delay + (max_delay - min_delay) * fraction
    return max(min_delay, min(max_delay, delay))


def split_reply(
    text: str,
    max_segments: int,
    max_chars_per_segment: int,
    rng: random.Random | None = None,
) -> list[str]:
    """Découpe la réponse du LLM en 1 à ``max_segments`` messages courts (S3).

    Règles :
    - texte vide : liste vide ;
    - texte qui tient dans un segment : un seul message ;
    - sinon, découpage de préférence aux fins de phrases (ponctuation forte
      ou retour à la ligne), puis aux frontières de mots pour les phrases
      trop longues ; un mot isolé plus long que la limite est coupé sans
      perte de contenu (rare : URL très longue) ;
    - le nombre de segments varie selon la longueur et une part aléatoire
      (S3 : éviter une mécanique toujours identique) : au moins
      ``ceil(longueur_réelle / max_chars_per_segment)``, au plus
      ``max_segments``. Sans générateur injecté, le nombre minimal
      nécessaire est conservé (déterminisme pour les tests) ;
    - chaque segment fait au plus ``max_chars_per_segment`` caractères,
      à l'exception du cas pathologique suivant : si la longueur réelle du
      texte (espaces de jointure compris) dépasse
      ``max_segments × max_chars_per_segment``, il est mathématiquement
      impossible de tenir à la fois « au plus ``max_segments`` segments »
      et « au plus ``max_chars_per_segment`` caractères ». Le repli
      ``_hard_split`` découpe alors en ``max_segments`` morceaux
      équilibrés : les segments peuvent dépasser la limite, mais il n'y a
      jamais de troncature ni de perte de contenu.

    La longueur qui pilote le calcul (``needed``, nombre de segments visé,
    budget de regroupement) est la longueur réelle du texte une fois les
    phrases regroupées — soit ``len(" ".join(chunks))`` — c'est-à-dire avec
    l'espace de jointure unique que ``_pack_chunks`` insère entre deux
    phrases. Ignorer ces espaces (somme brute des phrases) sous-estimerait
    le total et ferait dépasser la limite par segment ou produire plus de
    segments que nécessaire.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars_per_segment:
        return [text]

    chunks: list[str] = []
    for unit in _split_units(text):
        if len(unit) <= max_chars_per_segment:
            chunks.append(unit)
        else:
            chunks.extend(_split_long_unit(unit, max_chars_per_segment))

    # Longueur réelle du texte regroupé, espaces de jointure inclus : c'est
    # exactement la somme des longueurs des segments produits par _pack_chunks.
    total_len = len(" ".join(chunks))
    needed = math.ceil(total_len / max_chars_per_segment)
    target = _pick_segment_count(needed, max_segments, rng)
    if target > needed:
        # L'aléa (S3) demande plus de segments que le strict minimum : budget
        # réduit pour que le regroupement glouton en produise davantage.
        budget = max(1, math.ceil(total_len / target))
    else:
        # Nombre minimal requis (sans rng) ou cas pathologique (needed >
        # max_segments) : on offre la pleine largeur autorisée. Un budget plus
        # serré (ceil(total_len / needed)) laisserait des espaces de
        # jointure non comptabilisés dans chaque segment et ferait dépasser
        # le nombre minimal de segments.
        budget = max_chars_per_segment
    segments = _pack_chunks(chunks, budget)
    if len(segments) > max_segments:
        segments = _hard_split(text, max_segments)
    return [segment.strip() for segment in segments]


def _split_units(text: str) -> list[str]:
    """Découpe le texte en phrases, en gardant la ponctuation de fin (S3)."""
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


def _split_long_unit(unit: str, max_chars_per_segment: int) -> list[str]:
    """Découpe aux frontières de mots une phrase trop longue (S3)."""
    chunks: list[str] = []
    current = ""
    for word in unit.split():
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars_per_segment:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(word) > max_chars_per_segment:
            chunks.extend(_hard_split_word(word, max_chars_per_segment))
            current = ""
        else:
            current = word
    if current:
        chunks.append(current)
    return chunks


def _hard_split_word(word: str, max_chars: int) -> list[str]:
    """Coupe un mot isolé plus long que la limite, sans perte de contenu (rare)."""
    return [
        word[start : start + max_chars] for start in range(0, len(word), max_chars)
    ]


def _pack_chunks(chunks: list[str], budget: int) -> list[str]:
    """Regroupe les phrases en segments d'au plus ``budget`` caractères (S3)."""
    segments: list[str] = []
    current = ""
    for chunk in chunks:
        candidate = f"{current} {chunk}".strip() if current else chunk
        if current and len(candidate) > budget:
            segments.append(current)
            current = chunk
        else:
            current = candidate
    if current:
        segments.append(current)
    return segments


def _pick_segment_count(
    needed: int, max_segments: int, rng: random.Random | None
) -> int:
    """Nombre de segments visé : au moins ``needed``, au plus ``max_segments``.

    S3 demande que le nombre de messages varie (part aléatoire / longueur)
    pour éviter une mécanique toujours identique. Avec un générateur injecté,
    tirage uniforme entre ``needed`` et ``max_segments`` ; sans générateur,
    nombre minimal nécessaire (déterminisme des tests).
    """
    if needed >= max_segments:
        return max_segments
    if rng is None:
        return needed
    return rng.randint(needed, max_segments)


def _hard_split(text: str, max_segments: int) -> list[str]:
    """Découpe de secours en ``max_segments`` morceaux équilibrés (S3).

    Utilisée quand le regroupement par phrases produirait plus de segments
    que le maximum autorisé (texte très long, ou phrases dont les frontières
    empêchent le regroupement de tenir la cible) : on vise des morceaux de
    tailles proches, sans couper les mots, sans tronquer ni perdre le
    moindre contenu.

    Cas pathologique documenté : si ``len(text)`` dépasse
    ``max_segments × max_chars_per_segment``, la contrainte « au plus
    ``max_segments`` segments de au plus ``max_chars_per_segment``
    caractères » est irréalisable ; les morceaux équilibrés (environ
    ``len(text) / max_segments`` chacun) peuvent alors dépasser la limite
    par segment. On préfère conserver tout le contenu plutôt que tronquer.
    """
    if max_segments <= 1:
        return [text]
    words = text.split()
    target_len = math.ceil(len(text) / max_segments)
    segments: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if (
            current
            and len(candidate) > target_len
            and len(segments) < max_segments - 1
        ):
            segments.append(current)
            current = word
        else:
            current = candidate
    if current:
        segments.append(current)
    return segments