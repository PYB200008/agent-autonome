# Rapport de tests — Lot 1 « Il répond » (S4, S5, M1)

Date : 24 septembre 2026
Auteur : tester
Périmètre : socle du bot conversationnel Discord (DM filtré par ID, prompt persona, mémoire court terme).
Version : 1.1 — ajout du test d'exclusion des DM de groupe (S4, périmètre « groupes exclus »), 31 tests.

## Exigences couvertes

| Exigence | Couverture |
| --- | --- |
| S4 — Personnalité définie dans un fichier prompt, filtrage strict par ID | Oui |
| S5 — Ton oral en français : pas de liste, pas de mise en forme, pas de formule d'assistant | Oui |
| M1 — Court terme : les 30 derniers messages de la conversation en cours | Oui |
| Sécurité — le bot ignore tout message dont l'auteur n'est pas l'ID autorisé | Oui |
| Critère d'acceptation — « Un message d'un autre compte ne reçoit aucune réponse » | Oui |
| Temps simulé — horloge injectable, aucun test en temps réel | Oui |
| Robustesse — erreur LLM sans crash ni message parasite | Oui |
| Persistance — mémoire conservée après redémarrage (base SQLite temporaire) | Oui, pour les messages ; les relances (lot 4) seront testées à leur lot |

## Fichiers de tests

| Fichier | Module testé | Tests |
| --- | --- | --- |
| `tests/test_discord_client.py` | `bot/discord_client.py` | 7 |
| `tests/test_conversation.py` | `bot/conversation.py` | 4 |
| `tests/test_db.py` | `bot/db.py` | 5 |
| `tests/test_llm.py` | `bot/llm.py` | 4 |
| `tests/test_prompt_examples.py` | `prompts/exemples-conversation.md` | 6 |
| `tests/test_clock.py` | `bot/clock.py` | 2 |
| `tests/test_config.py` | `bot/config.py` | 3 |
| `tests/conftest.py`, `tests/fakes.py`, `tests/helpers.py` | support (fixtures, mocks) | — |

Total : 31 tests. Structure prévue pour accueillir les lots 2 à 5 (un fichier par module, fixtures communes dans `conftest.py`).

## Détail des tests par exigence

### Filtrage strict (S4 + sécurité)

- `test_guild_message_is_ignored` — Vérifie S4 : un message de serveur ne déclenche ni LLM ni envoi.
- `test_group_dm_is_ignored` — Vérifie S4 et le périmètre « groupes exclus » du cahier des charges : un DM de groupe (channel de type `group`, auteur autorisé, sans serveur) ne déclenche ni appel LLM ni envoi.
- `test_dm_from_other_account_is_ignored` — Vérifie S4 et le critère d'acceptation : un autre compte ne reçoit aucune réponse.
- `test_dm_from_bot_itself_is_ignored` — Vérifie S4 : le bot ignore ses propres messages, même avec l'identifiant autorisé.
- `test_dm_authorized_is_processed_and_replied` — Vérifie S4 : un DM de l'utilisateur autorisé déclenche le traitement puis l'envoi.
- `test_dm_with_blank_content_is_ignored` — Vérifie S4 (robustesse) : un message sans contenu n'est pas traité.
- `test_dm_authorized_full_flow` — Vérifie S4 et M1 de bout en bout : réponse envoyée et échange mémorisé.

Tous ces tests utilisent des objets messages simulés (`tests/fakes.py`) : aucun socket ni appel réseau.

### Mémoire court terme (M1)

- `test_insert_message_is_stored` — l'insertion d'un message crée la ligne en base (table `messages`).
- `test_recent_messages_limited_to_thirty_db` — la relecture ne renvoie que les 30 derniers messages, dans l'ordre chronologique, avec les rôles `utilisateur`/`bot` corrects.
- `test_same_user_gets_stable_conversation` — le même utilisateur retombe sur la même conversation ; un autre utilisateur obtient une conversation distincte.
- `test_generate_reply_sends_dated_context` — le contexte passé au LLM est daté (date et heure simulées) et contient les messages récents.
- `test_handle_incoming_context_limited_to_thirty` — le contexte réellement envoyé au LLM ne contient que les 30 derniers messages, datés, dans l'ordre.
- `test_memory_survives_database_restart` — persistance : fermeture puis réouverture de la base, messages conservés.

### Prompt et style (S4, S5)

- `test_system_prompt_injects_full_persona` — le contenu de `persona.md` est bien injecté dans le prompt système (placeholder remplacé, aucune trace résiduelle).
- `test_expected_outputs_are_read` — le fichier d'exemples est lu correctement (3 exemples + 1 variante).
- `test_no_assistant_formulas_in_examples` — Vérifie S5 : aucune formule d'assistant (« Bien sûr ! », « N'hésite pas... », etc.) dans les sorties attendues.
- `test_no_list_or_heading_in_examples` — Vérifie S5 : ni liste ni titre Markdown.
- `test_no_emoji_in_examples` — Vérifie S5 : ni emoji ni symbole parasite.
- `test_emoji_detection_works` / `test_list_detection_works` — contrôles positifs des détections.

### Temps simulé et robustesse

- `test_set_now_imposes_simulated_time` / `test_reset_now_restores_real_clock` — l'horloge injectable fonctionne et se réinitialise.
- `test_message_timestamp_follows_simulated_clock` — les horodatages insérés en base suivent le temps simulé.
- `test_generate_reply_logs_api_error_and_returns_none` — erreur API Anthropic loguée, renvoie `None`, pas de crash.
- `test_generate_reply_keeps_only_text_blocks` — seuls les blocs texte de la réponse API sont conservés.
- `test_handle_incoming_returns_none_on_api_error` — erreur LLM : aucun message bot inséré, silence propre.
- `test_handle_incoming_survives_unexpected_error` — exception inattendue : loguée, pas de reliquat.
- `test_load_config_requires_secrets` / `test_load_config_rejects_non_numeric_user_id` — configuration : jamais de secret réel, identifiant numérique exigé.

## Résultats

### pytest

```text
$ python -m pytest tests -q
31 passed, 1 warning in 1.04s
```

Durée totale d'exécution environ 1 seconde : aucun test n'attend en temps réel. Un seul warning, sans lien avec le code testé (voir anomalies).

### ruff

```text
$ ruff check bot main.py tests
All checks passed!
```

### mypy

```text
$ mypy bot main.py tests
Success: no issues found in 19 source files
```

## Anomalies et notes

1. **Stubs PyYAML manquants** : `mypy bot main.py` échouait sur `bot/config.py:16` (« Library stubs not installed for "yaml" »). Correctif trivial appliqué : ajout de `types-PyYAML>=6.0.0` dans `requirements.txt` (installé dans le venv). Aucune modification du code applicatif.
2. **Warning pytest** : `DeprecationWarning: 'audioop' is deprecated` provient de `discord/player.py` (dépendance amont discord.py, Python 3.12). Sans lien avec le lot 1 ; aucun impact sur les tests.
3. **Aucune modification du code applicatif** (`bot/`, `main.py`, `config.yaml`, `persona.md`, `prompts/`) n'a été nécessaire : le socle développé par bot-dev satisfait les tests du lot 1 tels quels.
4. **Suite à la relecture reviewer du lot 1** : l'exclusion explicite des DM de groupe demandée (`bot/discord_client.py`, filtre `message.channel.type != discord.ChannelType.private`) est couverte par le nouveau test `test_group_dm_is_ignored`. Le cas « DM privé autorisé → traité » reste vert (régression vérifiée dans la même série, 31 tests).
5. **Hors périmètre volontaire** : les états (C1-C6), le rythme (S1-S3, S6-S8) et les relances (R1-R8, y compris la persistance des relances planifiées) seront testés aux lots 2 à 4 ; la structure `tests/` (fixtures partagées, fakes, un fichier par module) est prête pour ces ajouts.

## Critères d'acceptation du lot 1

- [x] Un message d'un autre compte ne reçoit aucune réponse (testé : `test_dm_from_other_account_is_ignored`).
- [x] Aucune réponse ne contient de liste, de titre ou de formule d'assistant (testé sur les exemples du prompt : `test_prompt_examples.py`). Le respect par le vrai LLM sera re-vérifié au lot 3 avec le format JSON de sortie.