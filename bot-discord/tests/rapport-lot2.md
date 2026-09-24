# Rapport de tests — Lot 2 « Il parle comme quelqu'un » (S1–S3, S6–S8)

Date : 24 septembre 2026
Auteur : tester
Périmètre : rythme de réponse (délai S1, frappe S2, découpage S3), consignes de style S6-S7 dans les prompts, regroupement des rafales (S8).
Version : 1.1 — 69 tests, 0 échec. Depuis la 1.0 : correction de `split_reply` (S3, longueur réelle du texte regroupé prise en compte, cas pathologique documenté) verrouillée dans `tests/test_rhythm.py`.

## Exigences couvertes

| Exigence | Couverture |
| --- | --- |
| S1 — Délai avant réponse variable 3–60 s, proportionnel aux longueurs, part aléatoire | Oui (fonction pure `compute_reply_delay` + intégration client) |
| S2 — Indicateur « en train d'écrire » pendant le délai | Oui (fake `typing()` sur FakeChannel, ordre frappe → sommeil → envoi vérifié) |
| S3 — Réponse découpée en 1 à 3 messages courts, intervalle entre envois, robustesse à l'échec | Oui (fonction pure `split_reply` + intégration client + échec simulé) |
| S6 — Au plus une question par message, pas de question à chaque réponse | Oui (exemples 1–8 + section « Questions (S6) » de conversation.md) |
| S7 — Réponses brèves normales | Oui (exemples 3, 7, 8 + section « Réponses brèves (S7) » de conversation.md) |
| S8 — Messages consécutifs regroupés, un seul appel LLM | Oui (regroupement, rafales séparées, filtrage inchangé) |
| Temps simulé — aucun test n'attend en temps réel | Oui (faux sommeil `instant_sleep`, suite complète < 2 s) |
| Robustesse — réponse None (erreur LLM) sans envoi ni crash | Oui |

## Fichiers de tests

| Fichier | Module testé | Tests |
| --- | --- | --- |
| `tests/test_rhythm.py` | `bot/rhythm.py` (S1, S3) | 18 |
| `tests/test_discord_rhythm.py` | `bot/discord_client.py` (S1-S3, S8) | 6 |
| `tests/test_discord_client.py` | `bot/discord_client.py` (S4, filtrage) | 7 |
| `tests/test_prompt_examples.py` | `prompts/exemples-conversation.md`, `prompts/conversation.md` (S5-S7) | 13 |
| `tests/test_config.py` | `bot/config.py` (section rythme) | 7 |
| `tests/test_conversation.py` | `bot/conversation.py` (handle_burst, M1) | 4 |
| `tests/test_db.py`, `tests/test_llm.py`, `tests/test_clock.py` | socle lot 1 (inchangés) | 5 + 7 + 2 |
| `tests/conftest.py`, `tests/fakes.py`, `tests/helpers.py` | support (fixtures, mocks, temps simulé) | — |

Total : 69 tests, 0 échec.

## Détail des tests par exigence

### S1 — Délai de réponse (`tests/test_rhythm.py` + `tests/test_discord_rhythm.py`)

- `test_delay_is_bounded_for_any_draw` — délai dans [3, 60] pour 5 longueurs × 25 graines.
- `test_delay_is_proportional_to_lengths_with_fixed_rng` — à graine identique, échange plus long → délai supérieur.
- `test_delay_is_deterministic_when_weight_is_one` — poids 1 : le hasard disparaît, seules les longueurs comptent.
- `test_two_different_draws_give_different_delays` — la part aléatoire existe (graines 123 vs 456).
- `test_zero_length_weight_keeps_only_chance` — poids 0 : les longueurs sont ignorées, seul le tirage compte.
- `test_delay_saturates_at_reference_length` — saturation à la longueur de référence (400).
- `test_rejects_negative_lengths` — robustesse : ValueError sur longueur négative.
- `test_reply_delay_is_applied_with_typing_indicator` — intégration : l'envoi est précédé d'un délai dans [min, max] (l'attente de regroupement S8 puis le délai S1 sont observés, dans cet ordre).

### S2 — Indicateur « en train d'écrire »

- `test_reply_delay_is_applied_with_typing_indicator` — le fake `typing()` enregistre entrée/sortie ; le délai S1 est consommé pendant la frappe active (ordre : frappe → sommeil → envoi), et aucune frappe pendant l'attente de regroupement.

### S3 — Découpage (`tests/test_rhythm.py` + `tests/test_discord_rhythm.py`)

- `test_split_empty_text_returns_no_segment` / `test_split_short_text_returns_single_segment` — cas limites.
- `test_split_uses_minimum_segments_without_rng` — sans générateur : déterministe, minimalité stricte verrouillée sur la longueur réelle : « Phrase courte. » × 40 (599 caractères réels, espaces de jointure compris) → exactement 2 segments, chacun ≤ 300. L'assertion, assouplie en 1.0 (« quand le regroupement le permet »), est redevenue stricte après la correction de `bot/rhythm.py`.
- `test_split_respects_max_segments_and_length` — pour 5 textes tenables, la précondition (longueur réelle ≤ 3 × 300) est vérifiée explicitement, puis 1 à 3 segments chacun ≤ 300 caractères, sur 4 graines.
- `test_split_prefers_sentence_endings` — fin de phrase privilégiée, ponctuation attachée.
- `test_split_preserves_total_content` — aucun contenu perdu, aucun mot coupé (espaces normalisées).
- `test_split_is_deterministic_with_same_seed` / `test_split_varies_with_rng` — déterminisme à graine égale, variabilité du nombre de segments avec le générateur.
- `test_split_handles_isolated_word_longer_than_limit` — mot isolé > 300 (URL) : toujours découpé en dur, morceaux ≤ 300, tous les caractères préservés (les 400 caractères du mot long sont comptés dans les segments).
- `test_split_huge_text_keeps_content_and_word_boundaries` — texte trop long pour 3 × 300 : mots entiers conservés, contenu intact (la limite par message peut être dépassée, voir anomalies).
- `test_split_pathological_overflow_keeps_all_content` — cas pathologique documenté (« Phrase de test. » × 60 = 959 caractères réels > 3 × 300) : exactement 3 segments équilibrés, contenu intact à la normalisation près — le débordement de limite par segment y est admis, la troncature jamais.
- `test_long_reply_split_into_segments_with_interval` — intégration : réponse de 600 caractères envoyée en 2 ou 3 messages ≤ 300, intervalle configuré (2 s) entre les envois observé.
- `test_failed_segment_send_does_not_block_following` — échec d'envoi du premier segment logué, les suivants partent quand même.

### S8 — Regroupement des rafales

- `test_burst_grouping_single_llm_call` — deux messages rapides : un seul appel LLM, un seul envoi, les deux contenus dans le contexte dans l'ordre, les deux messages mémorisés en base.
- `test_bursts_separated_by_calm_are_two_rounds` — rafales séparées par une attente > délai de regroupement : deux appels, deux réponses.
- Filtrage inchangé (`test_discord_client.py`) : guild, groupe, autre compte, bot lui-même, contenu vide — aucun appel, aucune tâche de rafale créée (`_burst_task is None`, `_pending_contents == []`).
- `test_dm_authorized_is_processed_and_replied` / `test_dm_authorized_full_flow` — adaptés au traitement asynchrone : attente de la tâche via `helpers.wait_for_burst_processing` après `on_message` (faux sommeil instantané).

### S6 et S7 — Style dans les prompts (`tests/test_prompt_examples.py`)

- `test_expected_outputs_are_read` — 8 exemples (1 à 8) découverts, 10 sorties attendues (variantes des exemples 3 et 7 incluses).
- `test_at_most_one_question_per_output` — chaque sortie pose au plus une question (comptage des « ? », fiable : aucune citation intérieure).
- `test_some_outputs_have_no_question` — l'exemple 7 ne pose aucune question ; l'exemple 1 en pose une (le « au plus une » n'est pas un « jamais »).
- `test_brief_outputs_are_short` — exemple 7 : ≤ 5 mots et une seule ponctuation forte ; exemple 8 : ≤ 20 mots, sans question.
- `test_conversation_prompt_has_s6_and_s7_sections` — sections « Questions (S6) » et « Réponses brèves (S7) » présentes dans `prompts/conversation.md` avec leurs consignes.

### Configuration de la section rythme (`tests/test_config.py`)

- `test_rythme_defaults_loaded_when_section_absent` — les 8 valeurs par défaut sont chargées quand la section est absente.
- `test_rythme_rejects_min_greater_or_equal_max` — delai_min ≥ delai_max → ConfigError.
- `test_rythme_rejects_weight_out_of_range` — poids hors [0, 1] → ConfigError.
- `test_rythme_rejects_negative_burst_wait` — attente de regroupement négative → ConfigError.

## Résultats

### pytest

```text
$ python -m pytest tests -q
69 passed, 1 warning in 1.31s
```

Durée totale environ 1,3 seconde : aucun test n'attend en temps réel (faux sommeil `helpers.instant_sleep`, générateur `random.Random` injecté).

### ruff

```text
$ python -m ruff check bot main.py tests
All checks passed!
```

### mypy

```text
$ python -m mypy bot main.py tests
Success: no issues found in 22 source files
```

## Anomalies et points fragiles du code lot 2 (pour bot-dev)

1. **Correction `split_reply` (S3) : ancienne anomalie 1 et ancienne anomalie 2 de la version 1.0, résolues.** `bot/rhythm.py` prend désormais en compte la longueur réelle du texte regroupé (espaces de jointure compris) pour `needed` et le budget, et documente le cas pathologique (longueur réelle > max_segments × max_chars_per_segment : segments équilibrés pouvant dépasser la limite, jamais de perte de contenu). Vérifications en production : `split_reply("Phrase courte. " * 40, 3, 300)` → 2 segments de 299 (minimalité), `split_reply("Phrase de test. " * 60, 3, 300)` → 3 segments de 319 (pathologique documenté). Verrouillage dans les tests : `test_split_uses_minimum_segments_without_rng` (minimalité stricte, assertion assouplie en 1.0 redevenue stricte), `test_split_respects_max_segments_and_length` (précondition tenable vérifiée puis bornes par segment), `test_split_pathological_overflow_keeps_all_content` (959 caractères réels → exactement 3 segments, contenu intact), `test_split_handles_isolated_word_longer_than_limit` (mot > 300 toujours découpé en dur sans perte).

2. **Note de test** : `helpers.wait_for_burst_processing` suppose qu'une rafale a bien été mise en attente (message autorisé reçu) ; si elle était appelée après un message filtré, la boucle tournerait indéfiniment. Les tests de filtrage n'appellent pas ce helper et vérifient à l'inverse l'absence de tâche (`_burst_task is None`).

3. **Ordre des sommeils observés** : le premier sommeil enregistré dans les tests d'intégration est l'attente de regroupement S8 (3 s), le second le délai S1. Les tests S1/S3 en tiennent compte explicitement ; toute modification de l'ordre frappe/délai/envoi dans `_apply_rhythm_and_send` cassera `test_reply_delay_is_applied_with_typing_indicator` (comportement voulu : l'ordre est une exigence S2).

4. **Warning pytest** inchangé : `DeprecationWarning: 'audioop'` vient de `discord/player.py` (dépendance amont), sans lien avec le lot 2.

## Critères d'acceptation du lot 2

- [x] Délai avant réponse variable 3 à 60 s, proportionnel aux longueurs, avec part aléatoire (S1, testé en pur et en intégration).
- [x] « En train d'écrire » affiché pendant tout le délai (S2, ordre frappe → sommeil → envoi vérifié).
- [x] Réponse en 1 à 3 messages courts avec intervalle, échec d'envoi non bloquant (S3).
- [x] Messages consécutifs regroupés, un seul appel LLM (S8).
- [x] Au plus une question par message, pas de question à chaque réponse (S6, exemples 1–8).
- [x] Réponses brèves normales (S7, exemples 3, 7 et 8).
- [ ] Les relances planifiées et la mémoire conservées après redémarrage seront testées aux lots 3/4 (la persistance des messages est déjà couverte au lot 1).