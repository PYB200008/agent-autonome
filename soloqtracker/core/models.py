"""Modèles de données partagés entre les agents du tracker LoL."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GameStatus(Enum):
    """Statut d'une partie."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class TeamSide(Enum):
    """Côté de l'équipe."""

    BLUE = 100
    RED = 200


@dataclass
class Player:
    """Représente un joueur dans une partie."""

    puuid: str
    summoner_name: str
    champion_id: int
    champion_name: str
    team: TeamSide
    role: str | None = None
    rank: str | None = None
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    cs: int = 0
    gold: int = 0
    damage_to_champions: int = 0
    vision_score: int = 0
    items: list[int] = field(default_factory=list)
    level: int = 0


@dataclass
class Team:
    """Représente une équipe dans une partie."""

    team_id: int
    side: TeamSide
    players: list[Player] = field(default_factory=list)
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    gold: int = 0
    cs: int = 0
    dragons: int = 0
    barons: int = 0
    towers: int = 0


@dataclass
class Game:
    """Représente une partie suivie."""

    game_id: int
    match_id: str | None = None
    status: GameStatus = GameStatus.PENDING
    game_mode: str = ""
    game_duration: int = 0
    teams: list[Team] = field(default_factory=list)
    tracked_player_puuid: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# Mapping champion_id -> rôle principal pour les champions les plus courants.
# Utilisé pour estimer les rôles quand Spectator ne fournit pas l'info.
# Clé: championId Riot, Valeur: rôle.
CHAMPION_TO_ROLE: dict[int, str] = {
    # Top
    1: "top",       # Ashe (peut être top)
    2: "top",       # Olaf
    8: "top",       # Udyr
    31: "top",      # Cho'Gath
    36: "top",      # Dr. Mundo
    41: "top",      # Gangplank
    48: "top",      # Trundle
    58: "top",      # Renekton
    75: "top",      # Kennen
    80: "top",      # Pantheon
    82: "top",      # Mordekaiser
    83: "top",      # Yorick
    98: "top",      # Shen
    104: "top",     # Graves
    122: "top",     # Darius
    127: "top",     # Lissandra
    131: "top",     # Diana
    150: "top",     # Gnar
    154: "top",     # Zac
    157: "top",     # Yasuo
    164: "top",     # Camille
    223: "top",     # Tahm Kench
    233: "top",     # Briar
    254: "top",     # Vi
    360: "top",     # Samira
    420: "top",     # Illaoi
    421: "top",     # Rek'Sai
    516: "top",     # Ornn
    517: "top",     # Sylas
    777: "top",     # Yone
    800: "top",     # Smolder
    # Jungle
    19: "jungle",   # Warwick
    28: "jungle",   # Evelynn
    32: "jungle",   # Amumu
    56: "jungle",   # Nocturne
    60: "jungle",   # Elise
    76: "jungle",   # Nidalee
    107: "jungle",  # Rengar
    113: "jungle",  # Sejuani
    121: "jungle",  # Kha'Zix
    134: "jungle",  # Syndra
    203: "jungle",  # Kindred
    254: "jungle",  # Vi
    421: "jungle",  # Rek'Sai
    # Mid
    4: "mid",       # Twisted Fate
    5: "mid",       # Xin Zhao
    7: "mid",       # LeBlanc
    10: "mid",      # Kayle
    23: "mid",      # Irelia
    24: "mid",      # Jax
    38: "mid",      # Kassadin
    55: "mid",      # Katarina
    61: "mid",      # Orianna
    74: "mid",      # Viktor
    91: "mid",      # Talon
    92: "mid",      # Riven
    103: "mid",     # Ahri
    112: "mid",     # Vladimir
    114: "mid",     # Fiora
    127: "mid",     # Lissandra
    131: "mid",     # Diana
    134: "mid",     # Syndra
    142: "mid",     # Azir
    143: "mid",     # Zyra
    238: "mid",     # Zed
    245: "mid",     # Ekko
    266: "mid",     # Aatrox
    267: "mid",     # Nami
    429: "mid",     # Kalista
    432: "mid",     # Bard
    631: "mid",     # Pyke
    777: "mid",     # Yone
    910: "mid",     # Hwei
    # ADC
    22: "adc",      # Ashe
    42: "adc",      # Corki
    51: "adc",      # Caitlyn
    67: "adc",      # Vayne
    81: "adc",      # Ezreal
    96: "adc",      # Kog'Maw
    119: "adc",     # Draven
    129: "adc",     # Senna
    218: "adc",     # Pyke
    222: "adc",     # Jinx
    236: "adc",     # Lucian
    429: "adc",     # Kalista
    497: "adc",     # Xayah
    523: "adc",     # Aphelios
    # Support
    40: "support",  # Janna
    43: "support",  # Karma
    53: "support",  # Blitzcrank
    89: "support",  # Leona
    117: "support", # Lulu
    201: "support", # Braum
    235: "support", # Senna
    267: "support", # Nami
    412: "support", # Thresh
    497: "support", # Xayah (peut être support avec Rakan)
    555: "support", # Pyke
    631: "support", # Pyke
}

# Mapping Riot teamId → TeamSide
_TEAM_ID_MAP = {100: TeamSide.BLUE, 200: TeamSide.RED}


def _get_team_side(team_id: int) -> TeamSide:
    """Convertit un teamId Riot en TeamSide."""
    return _TEAM_ID_MAP.get(team_id, TeamSide.BLUE)


def _estimate_role(champion_id: int) -> str | None:
    """Estime le rôle d'un joueur basé sur son champion."""
    return CHAMPION_TO_ROLE.get(champion_id)


def parse_game_from_spectator(data: dict, puuid: str) -> Game:
    """Parse une réponse brute de Spectator-V5 en objet Game.

    Args:
        data: Dict JSON retourné par GET /lol/spectator/v5/active-games/by-summoner/{summonerId}.
        puuid: PUUID du joueur dont on suit la partie.

    Returns:
        Objet Game pré-rempli avec teams et joueurs.
    """
    game_id = getattr(data, "get", lambda k, d: d)("gameId", 0)
    game_mode = getattr(data, "get", lambda k, d: d)("gameMode", "")

    teams_map: dict[int, Team] = {}

    participants = data.get("participants", [])
    for p in participants:
        team_id = p.get("teamId", 100)
        if team_id not in teams_map:
            teams_map[team_id] = Team(
                team_id=team_id,
                side=_get_team_side(team_id),
            )

        player_puuid = p.get("puuid", "")
        champion_id = p.get("championId", 0)
        summoner_name = p.get("summonerName", "")

        player = Player(
            puuid=player_puuid,
            summoner_name=summoner_name,
            champion_id=champion_id,
            champion_name="",
            team=_get_team_side(team_id),
            role=_estimate_role(champion_id),
        )
        teams_map[team_id].players.append(player)

    teams = list(teams_map.values())

    return Game(
        game_id=game_id,
        status=GameStatus.IN_PROGRESS,
        game_mode=game_mode,
        teams=teams,
        tracked_player_puuid=puuid,
    )


def parse_game_from_match(data: dict, puuid: str) -> Game:
    """Parse une réponse brute de Match-V5 en objet Game complet.

    Args:
        data: Dict JSON retourné par GET /lol/match/v5/matches/{matchId}.
        puuid: PUUID du joueur dont on suit la partie.

    Returns:
        Objet Game avec toutes les stats (kills, assists, cs, etc.).
    """
    info = data.get("info", {})
    metadata = data.get("metadata", {})

    match_id = metadata.get("matchId", "")
    game_mode = info.get("gameMode", "")
    game_duration = info.get("gameDuration", 0)

    teams_map: dict[int, Team] = {}

    participants = info.get("participants", [])
    for p in participants:
        team_id = p.get("teamId", 100)
        if team_id not in teams_map:
            teams_map[team_id] = Team(
                team_id=team_id,
                side=_get_team_side(team_id),
            )

        champion_id = p.get("championId", 0)

        items = [
            p.get(f"item{i}", 0)
            for i in range(7)
        ]
        items = [item_id for item_id in items if item_id != 0]

        player = Player(
            puuid=p.get("puuid", ""),
            summoner_name=p.get("summonerName", ""),
            champion_id=champion_id,
            champion_name=p.get("championName", ""),
            team=_get_team_side(team_id),
            kills=p.get("kills", 0),
            deaths=p.get("deaths", 0),
            assists=p.get("assists", 0),
            cs=p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
            gold=p.get("goldEarned", 0),
            damage_to_champions=p.get("totalDamageDealtToChampions", 0),
            vision_score=p.get("visionScore", 0),
            items=items,
            level=p.get("champLevel", 0),
        )
        teams_map[team_id].players.append(player)

    # Récupérer les stats d'équipe depuis l'objet team de chaque team
    for team_obj in info.get("teams", []):
        team_id = team_obj.get("teamId", 0)
        if team_id in teams_map:
            team_stats = team_obj.get("objectives", {})
            kills_obj = team_stats.get("kills", {})
            deaths_obj = team_stats.get("deaths", {})
            assists_obj = team_stats.get("assists", {})
            dragons_obj = team_stats.get("dragon", {})
            barons_obj = team_stats.get("baron", {})
            towers_obj = team_stats.get("tower", {})

            t = teams_map[team_id]
            t.kills = kills_obj.get("kills", 0)
            t.deaths = deaths_obj.get("deaths", 0)
            t.assists = assists_obj.get("assists", 0)
            t.dragons = dragons_obj.get("kills", 0)
            t.barons = barons_obj.get("kills", 0)
            t.towers = towers_obj.get("kills", 0)

    # Agréger les stats gold/cs par équipe depuis les participants
    for t in teams_map.values():
        for player in t.players:
            t.gold += player.gold
            t.cs += player.cs

    teams = list(teams_map.values())

    return Game(
        game_id=0,
        match_id=match_id,
        status=GameStatus.FINISHED,
        game_mode=game_mode,
        game_duration=game_duration,
        teams=teams,
        tracked_player_puuid=puuid,
    )
