"""Tests unitaires du rythme de réponse (bot/rhythm.py, S1 et S3).

Deux fonctions pures, testées sans réseau ni temps réel : ``compute_reply_delay``
(S1 : délai variable borné, proportionnel aux longueurs, avec part aléatoire) et
``split_reply`` (S3 : découpage en 1 à 3 messages courts). Le générateur
aléatoire est injecté (``random.Random``) pour la reproductibilité.
"""

from __future__ import annotations

import random

import pytest  # type: ignore[import-untyped]

from bot.rhythm import compute_reply_delay, split_reply

MIN_DELAY = 3.0
MAX_DELAY = 60.0
LENGTH_WEIGHT = 0.6
REFERENCE_LENGTH = 400


# ---- compute_reply_delay (S1) ----


def test_delay_is_bounded_for_any_draw() -> None:
    """Vérifie S1 : quel que soit le tirage et la longueur de l'échange, le délai
    reste dans [delai_min_secondes, delai_max_secondes]."""
    for length in (0, 1, 50, 400, 5000):
        for seed in range(25):
            delay = compute_reply_delay(
                length,
                length,
                MIN_DELAY,
                MAX_DELAY,
                LENGTH_WEIGHT,
                REFERENCE_LENGTH,
                rng=random.Random(seed),
            )
            assert MIN_DELAY <= delay <= MAX_DELAY


def test_delay_is_proportional_to_lengths_with_fixed_rng() -> None:
    """Vérifie S1 : à tirage identique (même graine), un échange plus long donne
    un délai supérieur — la composante « longueurs » joue à rng fixé."""
    short = compute_reply_delay(
        10, 10, MIN_DELAY, MAX_DELAY, LENGTH_WEIGHT, REFERENCE_LENGTH, rng=random.Random(42)
    )
    long = compute_reply_delay(
        200, 10, MIN_DELAY, MAX_DELAY, LENGTH_WEIGHT, REFERENCE_LENGTH, rng=random.Random(42)
    )
    assert short < long


def test_delay_is_deterministic_when_weight_is_one() -> None:
    """Vérifie S1 : avec un poids de longueur de 1 (aucune part aléatoire), le
    délai ne dépend que des longueurs — deux tirages différents coïncident, une
    longueur différente donne un délai différent."""
    first_draw = compute_reply_delay(
        100, 100, MIN_DELAY, MAX_DELAY, 1.0, REFERENCE_LENGTH, rng=random.Random(1)
    )
    second_draw = compute_reply_delay(
        100, 100, MIN_DELAY, MAX_DELAY, 1.0, REFERENCE_LENGTH, rng=random.Random(2)
    )
    shorter_exchange = compute_reply_delay(
        100, 0, MIN_DELAY, MAX_DELAY, 1.0, REFERENCE_LENGTH, rng=random.Random(1)
    )
    assert first_draw == second_draw
    assert shorter_exchange < first_draw


def test_two_different_draws_give_different_delays() -> None:
    """Vérifie S1 : la part aléatoire existe — deux tirages distincts (graines
    différentes) donnent des délais différents pour le même échange."""
    first = compute_reply_delay(
        50, 50, MIN_DELAY, MAX_DELAY, LENGTH_WEIGHT, REFERENCE_LENGTH, rng=random.Random(123)
    )
    second = compute_reply_delay(
        50, 50, MIN_DELAY, MAX_DELAY, LENGTH_WEIGHT, REFERENCE_LENGTH, rng=random.Random(456)
    )
    assert first != second


def test_zero_length_weight_keeps_only_chance() -> None:
    """Vérifie S1 : poids de longueur 0 → seul le hasard compte, les longueurs
    n'influent plus ; deux tirages différents divergent."""
    short = compute_reply_delay(
        0, 0, MIN_DELAY, MAX_DELAY, 0.0, REFERENCE_LENGTH, rng=random.Random(7)
    )
    long = compute_reply_delay(
        10000, 10000, MIN_DELAY, MAX_DELAY, 0.0, REFERENCE_LENGTH, rng=random.Random(7)
    )
    assert short == long
    other_draw = compute_reply_delay(
        0, 0, MIN_DELAY, MAX_DELAY, 0.0, REFERENCE_LENGTH, rng=random.Random(8)
    )
    assert short != other_draw


def test_delay_saturates_at_reference_length() -> None:
    """Vérifie S1 : au-delà de la longueur de référence, la composante
    « longueurs » sature — avec un poids de 1, le délai atteint le maximum."""
    saturated = compute_reply_delay(
        1000, 1000, MIN_DELAY, MAX_DELAY, 1.0, REFERENCE_LENGTH
    )
    below = compute_reply_delay(
        399, 0, MIN_DELAY, MAX_DELAY, 1.0, REFERENCE_LENGTH
    )
    assert saturated == MAX_DELAY
    assert below < MAX_DELAY


def test_rejects_negative_lengths() -> None:
    """Vérifie S1 (robustesse) : une longueur négative (message ou réponse) est
    refusée par ValueError."""
    with pytest.raises(ValueError):
        compute_reply_delay(-1, 10, MIN_DELAY, MAX_DELAY, LENGTH_WEIGHT, REFERENCE_LENGTH)
    with pytest.raises(ValueError):
        compute_reply_delay(10, -5, MIN_DELAY, MAX_DELAY, LENGTH_WEIGHT, REFERENCE_LENGTH)


# ---- split_reply (S3) ----


def test_split_empty_text_returns_no_segment() -> None:
    """Vérifie S3 : un texte vide (ou blanc) ne produit aucun message."""
    assert split_reply("", 3, 300) == []
    assert split_reply("   \n  ", 3, 300) == []


def test_split_short_text_returns_single_segment() -> None:
    """Vérifie S3 : un texte qui tient dans un message n'est pas découpé."""
    assert split_reply("coucou, ça va ?", 3, 300) == ["coucou, ça va ?"]


def test_split_uses_minimum_segments_without_rng() -> None:
    """Vérifie S3 : sans générateur injecté, le découpage est déterministe et
    atteint strictement le nombre minimal de segments — la longueur prise en
    compte est la longueur réelle du texte regroupé (espaces de jointure
    comprises) : 40 phrases de 14 caractères (599 caractères réels) tiennent
    en exactement 2 segments, chacun ≤ 300."""
    text = ("a" * 154 + ". ") + ("b" * 154 + ".")
    segments = split_reply(text, 3, 300)
    assert len(segments) == 2
    assert all(len(segment) <= 300 for segment in segments)
    # 40 phrases de 14 caractères : 599 caractères réels une fois regroupées
    # (14 × 40 + 39 espaces de jointure), minimum mathématique = ceil(599/300)
    # = 2 segments. La minimalité est verrouillée, pas assouplie.
    uniform = "Phrase courte. " * 40
    assert len(" ".join(["Phrase courte."] * 40)) == 599
    minimal = split_reply(uniform, 3, 300)
    assert len(minimal) == 2
    assert all(len(segment) <= 300 for segment in minimal)
    # Déterminisme : le même texte redonne exactement le même découpage.
    assert split_reply(uniform, 3, 300) == split_reply(uniform, 3, 300)


def test_split_respects_max_segments_and_length() -> None:
    """Vérifie S3 : pour tout texte tenable — longueur réelle (espaces de
    jointure comprises) inférieure ou égale à max_segments ×
    max_longueur_message — chaque segment fait au plus max_longueur_message
    caractères et le nombre de segments reste entre 1 et max_segments, quelle
    que soit la graine du générateur injecté."""
    texts = (
        "Phrase de test. " * 15,
        "Phrase de test. " * 30,
        "Phrase de test. " * 45,
        "Phrase courte. " * 40,
        "Une phrase normale du quotidien. " * 18,
    )
    for text in texts:
        # Textes uniformes : la longueur réelle du texte regroupé (espaces de
        # jointure uniques entre phrases) vaut len(text.strip()).
        assert len(text.strip()) <= 3 * 300
        for seed in (0, 1, 7, 42):
            segments = split_reply(text, 3, 300, rng=random.Random(seed))
            assert 1 <= len(segments) <= 3
            assert all(len(segment) <= 300 for segment in segments)


def test_split_prefers_sentence_endings() -> None:
    """Vérifie S3 : le découpage a lieu de préférence aux fins de phrases — la
    ponctuation reste attachée à la phrase qui la précède (aucun segment ne
    finit au milieu d'une phrase)."""
    text = "Phrase de test. " * 40
    for segment in split_reply(text, 3, 300):
        assert segment.endswith(".")


def test_split_preserves_total_content() -> None:
    """Vérifie S3 : aucun contenu n'est perdu — la réunion des segments (espaces
    normalisées) redonne le texte d'origine, aucun mot n'est coupé au milieu."""
    text = "Des mots tout à fait normaux, une phrase banale en entier. " * 15
    segments = split_reply(text, 3, 300)
    assert " ".join(" ".join(segments).split()) == " ".join(text.split())


def test_split_is_deterministic_with_same_seed() -> None:
    """Vérifie S3 : le même texte et la même graine donnent un découpage identique."""
    text = "Phrase de test. " * 45
    assert split_reply(text, 3, 300, rng=random.Random(9)) == split_reply(
        text, 3, 300, rng=random.Random(9)
    )


def test_split_varies_with_rng() -> None:
    """Vérifie S3 : avec un générateur injecté, le nombre de segments varie
    entre le minimum nécessaire et max_messages_reponse — 19 phrases de test
    (303 caractères réels, espaces de jointure comprises) donnent 2 segments
    minimum, certaines graines en produisent 3 (éviter une mécanique toujours
    identique)."""
    text = "Phrase de test. " * 19
    counts = {len(split_reply(text, 3, 300, rng=random.Random(seed))) for seed in range(40)}
    assert counts <= {2, 3}
    assert 2 in counts
    assert 3 in counts


def test_split_handles_isolated_word_longer_than_limit() -> None:
    """Vérifie S3 : un mot isolé plus long que la limite (URL) est toujours
    découpé en dur, sans perte de contenu — cas rare documenté dans
    bot/rhythm.py. Chaque segment reste sous la limite et tous les caractères
    du texte sont préservés dans l'ordre (les espaces insérées entre les
    morceaux du mot long sont ignorées)."""
    long_word = "h" * 400
    text = f"voilà le lien {long_word} et puis c'est tout"
    segments = split_reply(text, 3, 300)
    assert all(len(segment) <= 300 for segment in segments)
    assert " ".join(segments).replace(" ", "") == text.replace(" ", "")
    # Le mot long est découpé en dur : ses 400 caractères sont tous présents,
    # contigus une fois les espaces retirées, aucun morceau n'est perdu.
    assert sum(segment.count("h") for segment in segments) == 400


def test_split_huge_text_keeps_content_and_word_boundaries() -> None:
    """Vérifie S3 : pour un texte trop long pour tenir dans max_messages_reponse
    messages de la taille limite, le découpage de secours conserve tous les mots
    entiers et tout le contenu. Note de conception : la limite par message peut
    être dépassée dans ce cas — on préfère ne rien perdre plutôt que tronquer."""
    text = "Une phrase normale du quotidien, sans mot géant. " * 35
    segments = split_reply(text, 3, 300)
    assert len(segments) == 3
    assert all(segment.split() for segment in segments)
    assert " ".join(" ".join(segments).split()) == " ".join(text.split())


def test_split_pathological_overflow_keeps_all_content() -> None:
    """Vérifie S3 (cas pathologique documenté dans bot/rhythm.py) : un texte
    dont la longueur réelle dépasse max_segments × max_longueur_message est
    découpé en exactement max_segments segments équilibrés, sans perte de
    contenu. La limite par segment peut y être dépassée (contrainte
    irréalisable mathématiquement), mais rien n'est tronqué."""
    text = "Phrase de test. " * 60
    assert len(text.strip()) == 959  # longueur réelle > 3 × 300
    segments = split_reply(text, 3, 300)
    assert len(segments) == 3
    assert " ".join(" ".join(segments).split()) == " ".join(text.split())