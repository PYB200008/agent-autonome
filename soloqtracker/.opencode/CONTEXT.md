# Contexte du projet — Tracker LoL temps réel

## Stack technique
- Python 3.11+
- httpx (HTTP async) + tenacity (retry/backoff)
- Webhooks Discord (appels HTTP directs, pas de bot)
- SQLite (stockage d'état)
- asyncio (orchestration)

## Architecture agents
```
soloqtracker/
├── agents/
│   ├── watcher.py          # Agent 1 : poll Spectator-V5, détecte début de game
│   ├── collector.py        # Agent 2 : stats live via Live Client Data API (optionnel, v2)
│   └── match_fetcher.py    # Agent 3 : stats finales post-game via Match-V5
├── core/
│   ├── riot_api.py         # Wrapper API Riot (auth, rate limit, retry)
│   ├── models.py           # Structures de données (Game, Player, Stats)
│   ├── db.py               # Accès SQLite
│   └── discord_webhook.py  # Agent 4 : envoi d'embeds via webhook Discord
├── config.py               # Lecture .env et paramètres
├── main.py                 # Orchestrateur (lance les agents)
├── .env                    # Secrets (gitignoré)
├── .env.example            # Template .env
├── links.txt               # Secrets sensibles (gitignoré)
└── requirements.txt
```

## Endpoints Riot API
| Endpoint | Route | Usage |
|---|---|---|
| Account-V1 | GET /riot/account/v1/accounts/by-riot-id/{tagline}/{game} | Riot ID → PUUID (routage régional Europe, PAS euw1) |
| Spectator-V5 | GET /lol/spectator/v5/active-games/by-summoner/{summonerId} | Game en cours |
| Match-V5 | GET /lol/match/v5/matches/{matchId} | Stats détaillées post-game |
| Match-V5 | GET /lol/match/v5/matches/by-puuid/{puuid}/ids | Historique de matchs |
| League-V4 | GET /lol/league/v4/entries/by-summoner/{summonerId} | Rang/LP |

## Discord — Webhook
- Pas de bot Discord (pas de token, pas de discord.py)
- Envoi d'embeds via appels HTTP POST vers `DISCORD_WEBHOOK_URL`
- 2 embeds : Phase 1 (composition, en début de game) + Phase 2 (résultat, en fin de game)

## Rate limits Riot API (clé dev)
- 20 requêtes / seconde
- 100 requêtes / 2 minutes
- Backoff exponentiel sur 429

## Base URL par région
- EUW1: `https://euw1.api.riotgames.com` (région locale : Summoner-V4, Spectator-V5, League-V4)
- Routes Match-V5 et Account-V1: `https://europe.api.riotgames.com`

## Formats de données partagés
Les agents communiquent via des dataclasses Python standardisées. Voir `core/models.py` pour les schémas.
Le webhook reçoit des objets `Game` via des callbacks.

## Variables d'environnement (fichier .env, gitignoré)
| Variable | Obligatoire | Description |
|---|---|---|
| `RIOT_API_KEY` | Oui | Clé API Riot Games |
| `RIOT_REGION` | Non (défaut euw1) | Région de routage |
| `DISCORD_WEBHOOK_URL` | Oui | URL du webhook Discord |
| `TRACKED_PUUIDS` | Non | PUUIDs des comptes suivis (séparés par des virgules) |
| `WATCHER_INTERVAL` | Non (défaut 60) | Intervalle de poll du Watcher (secondes) |
| `DB_PATH` | Non (défaut tracker.db) | Chemin du fichier SQLite |

## Règles de versionnement
- Commit au nom de "William Bellon"
- Messages de commit clairs, à la 1ère personne
- Jamais de secrets dans le repo (clé API, webhook URL)
- Le .env et links.txt sont toujours gitignorés
