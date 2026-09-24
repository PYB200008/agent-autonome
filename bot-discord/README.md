# Bot conversationnel Discord

Bot Discord qui discute en message privé (DM) avec le seul utilisateur autorisé
(scotobi), comme le ferait une personne : il répond, pose des questions, sent
quand une conversation est finie et revient de lui-même après un délai aléatoire.
Le badge « APP » reste visible ; l'effet « personne normale » vient du
comportement (rythme, silences, relances, ton, mémoire).

Périmètre : DM avec scotobi uniquement. Exclu : serveurs, groupes, self-bot,
actions automatisées, messages vocaux, interface web.

## Lots

| Lot | Contenu | Exigences |
| --- | --- | --- |
| 1 — Il répond | Bot en DM, filtre sur l'ID, LLM + personnalité, mémoire court terme | S4, S5, M1 |
| 2 — Il parle comme quelqu'un | Délais variables, indicateur « en train d'écrire », messages découpés, regroupement | S1–S3, S6–S8 |
| 3 — Il sent la fin | États, détection de clôture, résumés de fin | C1–C6, M2 |
| 4 — Il revient | Relances aléatoires avec garde-fous, choix du sujet | R1–R8 |
| 5 — Il se souvient | Faits durables, commande `!oublie` | M3–M5 |

Exigences couvertes au lot 1 :

- S4 — personnalité définie dans un fichier prompt (`persona.md`), DM filtré
  sur l'ID de scotobi ;
- S5 — ton oral en français : phrases courtes, pas de listes, pas de mise en
  forme, pas de formules d'assistant ;
- M1 — mémoire court terme : les 30 derniers messages de la conversation en
  cours réinjectés dans le contexte envoyé au LLM.

Exigences couvertes au lot 2 :

- S1 — délai de réponse variable (3 à 60 s par défaut), proportionnel aux
  longueurs du message reçu et de la réponse, avec une part aléatoire ;
  formule et bornes dans la section `rythme` de `config.yaml` ;
- S2 — indicateur « en train d'écrire » affiché pendant tout le délai ;
- S3 — réponse découpée en 1 à 3 messages courts, envoyés avec un petit
  intervalle ; un échec d'envoi ne bloque pas les segments suivants ;
- S8 — messages consécutifs regroupés : le bot attend quelques secondes après
  le dernier message d'une rafale, puis répond à l'ensemble (un seul appel
  LLM).

## Prérequis

- Python 3.12.
- `pip install -r requirements.txt`

## Création et configuration du bot Discord

1. Ouvrir le portail développeur Discord (<https://discord.com/developers/applications>)
   et créer une application.
2. Créer un compte bot (section Bot). Le token du bot est affiché dans cette
   section : le copier dans `.env` (voir Configuration) sans jamais le montrer,
   le committer ni le logguer.
3. Activer les intents requis dans les réglages du bot :
   - `dm_messages` (messages privés) ;
   - `message_content` (contenu des messages).

## Configuration

1. Copier `.env.example` en `.env` et remplir les valeurs :
   - `DISCORD_TOKEN` : token du compte bot (Developer Portal > Bot) ;
   - `DISCORD_USER_ID` : ID numérique de scotobi. Pour l'obtenir : activer le
     mode développeur dans Discord (Paramètres > Avancé > Mode développeur),
     puis clic droit sur le pseudo de l'utilisateur > Copier l'ID de
     l'utilisateur ;
   - `GROQ_API_KEY` : clé API Groq (gratuite sur <https://console.groq.com/>).
2. `config.yaml` centralise tous les seuils (mémoire, LLM, chemins) : aucune
   valeur de seuil n'est codée en dur dans le code (exigence R8). Pour changer
   un seuil, modifier ce fichier.
3. `persona.md` définit la personnalité du bot, injectée dans le prompt système.
   `prompts/conversation.md` contient le prompt de conversation.

## Lancement

```
python main.py
```

## Tests

```
python -m pytest tests -q
ruff check bot main.py tests
mypy bot main.py tests
```

## Règles de sécurité

- Ne jamais committer `.env` (secrets), la base SQLite (`bot.db`) ni les logs.
- Le token et la clé API restent hors dépôt Git et hors logs.
- Le bot ignore tout message dont l'auteur n'est pas l'ID numérique de scotobi
  et tout message hors DM privé (serveurs et groupes exclus).