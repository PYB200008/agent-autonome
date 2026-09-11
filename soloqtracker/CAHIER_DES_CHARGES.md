# Cahier des charges — Tracker LoL temps réel (Python + Riot API + Discord)

## 1. Objectif du projet

Développer un système qui suit en temps réel une partie de League of Legends en cours (la sienne ou celle d'un joueur suivi) et publie automatiquement les statistiques clés dans un salon Discord via un bot, du début de partie jusqu'au résultat final.

**Cas d'usage cible** : suivre ses propres games (ou celles d'amis/du stream) sans avoir à ouvrir le client, avec un résumé automatique posté sur Discord.

---

## 2. Périmètre fonctionnel

### 2.1 Détection de partie
- Poll périodique de l'API Riot pour détecter le début d'une game pour un ou plusieurs `summonerPUUID` suivis (liste de comptes en config).
- Détection de fin de partie (via Match-V5 dès que le match_id devient disponible).

### 2.2 Statistiques suivies (stats "normales", pas de metrics exotiques)
**Pré-game**
- Champions sélectionnés (les 10), rôles, side (Blue/Red)
- Rangs des joueurs (si dispo via League-V4)

**En cours de partie** (si Spectator/Live Client Data dispo)
- Score (kills/deaths/assists) par équipe
- Or total et CS par joueur
- Objectifs pris (dragons, hérault, tourelles, baron)
- Niveau des champions

**Post-game (Match-V5, source la plus fiable)**
- KDA individuel et par équipe
- CS/min, Gold/min
- Dégâts infligés aux champions
- Vision score
- Résultat (victoire/défaite) et durée de la game
- Item build final (optionnel, affichage simple)

### 2.3 Sortie Discord — 2 phases d'annonce

**Phase 1 — Pendant la game (stats de base)**
- Message posté dès la détection de la game : composition des 10 champions, rôles, side, rangs des joueurs.
- Puis, si le tracker tourne sur la machine qui joue (voir contrainte §4), messages de mise à jour périodiques (ex. toutes les 2-3 min) avec les stats de base en direct : score par équipe, CS, or, niveau.
- Si le tracker tourne à distance (pas sur le PC qui joue), la Phase 1 se limite à la composition + rangs, sans live score (limite Riot API, voir §4).

**Phase 2 — Après la game (stats complètes)**
- Un message "Résultat" dès la fin de partie : victoire/défaite, durée, KDA détaillé par joueur, CS/min, Gold/min, dégâts, vision score, items finaux.

- Format : embeds Discord simples et lisibles (pas de dashboard complexe), un embed par annonce.

---

## 3. Architecture technique — approche multi-agents

Le volume d'appels API et la nature temps réel justifient une séparation en **plusieurs agents/processus indépendants**, communiquant via une file ou une base légère (évite qu'un composant lent/bloquant ne casse tout le pipeline) :

| Agent | Rôle | Fréquence |
|---|---|---|
| **Agent 1 — Watcher** | Poll `spectator-v5` (Active Games) pour chaque compte suivi, détecte le début d'une game | Toutes les 60s |
| **Agent 2 — Collector** | Une fois une game détectée, récupère les stats de base en direct (score, or, CS via Live Client Data API si tracker local) et transmet les updates au bot | Toutes les 2-3 min pendant la game |
| **Agent 3 — Match Fetcher** | Dès la fin de game, interroge `match-v5` pour les stats finales complètes | Déclenché en fin de partie |
| **Agent 4 — Discord Publisher** | Bot Discord qui reçoit les données formatées (via queue/DB) et poste les embeds | Événementiel |

**Communication entre agents** : fichier/table SQLite partagée ou file (ex. `queue` Python simple, ou Redis si tu veux aller plus loin) contenant l'état de chaque game suivie (`pending`, `in_progress`, `finished`).

*Note* : pour une v1 simple, les agents 1-2-3 peuvent tourner comme un seul script séquentiel avec state machine ; la séparation en process distincts devient utile si tu veux suivre **plusieurs comptes en parallèle** sans bloquer.

---

## 4. Endpoints Riot API à utiliser

| Endpoint | Usage |
|---|---|
| `ACCOUNT-V1` | Résoudre Riot ID → PUUID |
| `SUMMONER-V4` | PUUID → summonerId (si besoin pour d'autres endpoints legacy) |
| `SPECTATOR-V5` (Active Games) | Détecter si une game est en cours |
| `MATCH-V5` (by PUUID / by matchId) | Récupérer les stats détaillées post-game |
| `LEAGUE-V4` | Rang/LP des joueurs (optionnel) |

⚠️ **Contraintes API à respecter**
- Rate limit clé de développement : 20 req/1s et 100 req/2min (par défaut) → prévoir un throttling/retry (backoff exponentiel sur 429).
- La clé de dev expire toutes les 24h → prévoir un mécanisme de reload de clé ou passer en clé de prod si projet durable.
- Pas de "live spectator data" détaillée officiellement disponible hors client (le endpoint Spectator ne donne que la composition, pas le score live) → pour du vrai live tracking (or/CS en temps réel), il faudrait passer par la **Live Client Data API locale** (`127.0.0.1:2999`), disponible uniquement si le tracker tourne sur la machine qui joue la game.

---

## 5. Stack technique proposée

- **Langage** : Python 3.11+
- **Discord** : appels HTTP vers un webhook (pas de bot, pas de discord.py)
- **HTTP client** : `httpx` + gestion retry (`tenacity`)
- **Stockage d'état** : SQLite (via `sqlite3` ou `sqlmodel`) — suffisant pour ce volume
- **Scheduler** : `asyncio` (boucles async) pour les polls périodiques
- **Config** : fichier `.env` (clé API Riot, URL webhook Discord, liste comptes suivis)

---

## 6. Structure de projet suggérée

```
lol-tracker/
├── agents/
│   ├── watcher.py         # Agent 1
│   ├── collector.py       # Agent 2
│   ├── match_fetcher.py   # Agent 3
│   └── discord_bot.py     # Agent 4
├── core/
│   ├── riot_api.py        # Wrapper API Riot (auth, retry, rate limit)
│   ├── models.py          # Structures de données (Game, Player, Stats)
│   └── db.py               # Accès SQLite
├── config.py
├── .env
└── main.py                 # Orchestrateur (lance les agents)
```

---

## 7. Livrables attendus

1. Script fonctionnel détectant automatiquement une game pour un compte donné
2. Bot Discord connecté et postant un embed de composition en début de game
3. Bot Discord postant un embed de résultat/stats en fin de game
4. Fichier de config permettant d'ajouter/retirer des comptes suivis facilement
5. Gestion propre des erreurs API (rate limit, game non trouvée, clé expirée)

---

## 8. Risques / points de vigilance

- **Clé API dev = limite forte** → tester avec 1-2 comptes seulement au départ.
- **Pas de vraie donnée live sans Live Client Data API locale** → bien clarifier dès le départ si l'objectif est "live in-game" (nécessite d'être sur le PC qui joue) ou "détection + résumé post-game" (faisable à distance, plus simple).
- **Multi-comptes en parallèle** → attention à la consommation du rate limit global, prévoir une file d'attente si plusieurs games sont actives en même temps.

---

## 9. Prochaine étape suggérée

Commencer par une v1 minimaliste : **Agent 1 + Agent 3 + Agent 4 fusionnés en un seul script**, un seul compte suivi, résumé post-game uniquement. Ajouter la détection live et le multi-comptes une fois la base stable.
