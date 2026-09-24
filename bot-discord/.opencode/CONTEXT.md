# Contexte projet — Bot conversationnel Discord

Références : `CAHIER_DES_CHARGES.md` (source de vérité des exigences), `.opencode/tracking.json` (avancement par lot).

## Objectif

Un bot sur un compte bot Discord officiel qui discute en DM avec un seul utilisateur (scotobi) comme le ferait une personne : il répond, pose des questions, sent quand une conversation est finie et relance de lui-même après un délai aléatoire. Le badge « APP » reste visible ; l'effet « personne normale » vient du comportement (rythme, silences, relances, ton, mémoire).

Périmètre : DM avec scotobi uniquement. Exclu : serveurs, groupes, self-bot, actions automatisées, messages vocaux, interface web.

## Équipe et workflow

- orchestrateur : analyse le lot concerné, délègue, consolide, valide.
- bot-dev : tout le code Python (discord.py, états, relances, mémoire, SQLite, config).
- persona-designer : `persona.md`, prompts système, format de sortie du LLM. Toute décision ouverte du cahier des charges est signalée à l'orchestrateur, jamais tranchée seule.
- tester : tests pytest en temps simulé, mocks Discord/LLM, lint, rapport Markdown.
- reviewer : relecture finale obligatoire de chaque lot (sécurité, conformité, robustesse, anti-bruit, documentation).

Règles : ne passer au lot suivant que lorsque les tests du lot courant passent ; terminer chaque lot par une relecture reviewer avant de valider.

## Lots

| Lot | Contenu | Exigences |
| --- | --- | --- |
| 1 — Il répond | Bot en DM, filtre sur l'ID, LLM + personnalité, mémoire court terme | S4, S5, M1 |
| 2 — Il parle comme quelqu'un | Délais variables, indicateur « en train d'écrire », messages découpés, regroupement | S1–S3, S6–S8 |
| 3 — Il sent la fin | États, détection de clôture, résumés de fin | C1–C6, M2 |
| 4 — Il revient | Relances aléatoires avec garde-fous, choix du sujet | R1–R8 |
| 5 — Il se souvient | Faits durables, commande `!oublie` | M3–M5 |

## Exigences en un mot

- C1–C6 : états Active / En pause (silence > 10 min) / Terminée (silence > 2 h ou clôture jugée par le LLM) / Relance planifiée. Sortie JSON du LLM à chaque réponse : `{"reponse": [...], "conversation_finie": bool}`. Un résumé est généré en fin de conversation ; si l'utilisateur écrit pendant qu'une relance est planifiée, elle est annulée.
- R1–R8 : délai triangulaire (3 h · 10 h · 30 h), aucune relance 23 h–9 h (report aléatoire 9 h–12 h), délai ×3 après une relance ignorée, arrêt après 2 relances ignorées consécutives, plafond 2 relances/jour, angle choisi par le LLM parmi les derniers résumés, pas de répétition des 3 sujets précédents, tout paramètre dans `config.yaml` sans toucher au code.
- S1–S8 : délai de réponse 3 à 60 s (proportionnel aux longueurs + part aléatoire), indicateur « en train d'écrire », réponse en 1 à 3 messages courts, personnalité dans `persona.md`, ton oral en français (phrases courtes, pas de listes, pas de mise en forme, pas de formules d'assistant), au plus une question par message et pas à chaque réponse, réponses brèves possibles, messages consécutifs de l'utilisateur regroupés (attente de quelques secondes après le dernier).
- M1–M5 : court terme = 30 derniers messages ; long terme = résumé de 3 à 5 lignes par conversation terminée (date, sujets) ; faits durables extraits et mis à jour ; contexte envoyé au LLM = prompt de personnalité + faits durables + 5 derniers résumés + messages récents + date et heure actuelles ; commande DM `!oublie` qui efface toute la mémoire.

## Stack

Python 3.12 · discord.py 2.x (intents DM + `message_content`) · API Groq, compatible OpenAI (décision utilisateur) · `discord.ext.tasks` (boucle de fond 60 s) · SQLite (`messages`, `conversations`, `resumes`, `faits`, `relances`) · `.env` (secrets) + `config.yaml` (seuils) + `persona.md`. Un seul processus. Relances persistées en base pour survivre à un redémarrage. Horloge injectable (`now()` centralisée) pour les tests en temps simulé.

## Règles de format

- Aucun emoji, aucun bruit (caractères chinois, symboles parasites, encodage cassé).
- Commentaires et docstrings en français ; identifiants de code en anglais.
- Tests : noms de tests en anglais, docstrings en français citant l'exigence (ex. « Vérifie R4 »).
- Aucune valeur de seuil en dur : tout passe par `config.yaml` ou `.env`.
- Aucun secret dans le code, les logs, les tests ou l'historique git.

## Règles de versionnement

- Après chaque tâche terminée ou correction livrée : commit puis push.
- Identité git (nom, e-mail) et token lus depuis `.env` (gitignoré).
- Message de commit : clair et précis, à la première personne, citant l'exigence concernée quand c'est pertinent (ex. « Ajoute le report des relances hors heures calmes (R2) »).
- Ne jamais committer `.env`, la base SQLite, les logs ni aucun secret (token Discord, clé API).
