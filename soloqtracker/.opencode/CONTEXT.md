# Contexte du projet — Tracker LoL temps réel

## Stack technique
- Python 3.11+
- httpx (HTTP async) + tenacity (retry/backoff)
- discord.py 2.x (bot Discord)
- SQLite (stockage d'état)
- asyncio (orchestration)

## Architecture agents
```
soloqtracker/
├── agents/
│   ├── watcher.py          # Agent 1 : poll Spectator-V5, détecte début de game
│   ├── collector.py        # Agent 2 : stats live via Live Client Data API (optionnel, v2)
│   ├── match_fetcher.py    # Agent 3 : stats finales post-game via Match-V5
│   └── discord_bot.py      # Agent 4 : bot Discord, embeds composition + résultat
├── core/
│   ├── riot_api.py         # Wrapper API Riot (auth, rate limit, retry)
│   ├── models.py           # Structures de données (Game, Player, Stats)
│   └── db.py               # Accès SQLite
├── config.py               # Lecture .env et paramètres
├── main.py                 # Orchestrateur (lance les agents)
├── .env                    # Secrets (gitignoré)
├── .env.example            # Template .env
└── requirements.txt
```

## Endpoints Riot API
| Endpoint | Route | Usage |
|---|---|---|
| Account-V1 | GET /riot/account/v1/accounts/by-riot-id/{tagline}/{game} | Riot ID → PUUID |
| Spectator-V5 | GET /lol/spectator/v5/active-games/by-summoner/{summonerId} | Game en cours |
| Match-V5 | GET /lol/match/v5/matches/{matchId} | Stats détaillées post-game |
| Match-V5 | GET /lol/match/v5/matches/by-puuid/{puuid}/ids | Historique de matchs |
| League-V4 | GET /lol/league/v4/entries/by-summoner/{summonerId} | Rang/LP |

## Rate limits Riot API (clé dev)
- 20 requêtes / seconde
- 100 requêtes / 2 minutes
- Backoff exponentiel sur 429

## Base URL par région
- EUW1: `https://euw1.api.riotgames.com`
- Route matchs (Match-V5): `https://europe.api.riotgames.com`

## Formats de données partagés
Les agents communiquent via des dictionnaires Python standardisés. Voir `core/models.py` pour les schémas.

## Règles de versionnement
- Commit au nom de "William Bellon"
- Messages de commit clairs, à la 1ère personne
- Jamais de secrets dans le repo ( cle API, token Discord)
- Le .env est toujours gitignoré
