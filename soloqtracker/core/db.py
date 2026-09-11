"""Accès SQLite pour le stockage d'état des games suivies.

Fournit des fonctions pour initialiser la base, sauvegarder/récupérer
des objets Game et mettre à jour leur statut.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from core.models import Game, GameStatus, Player, Team, TeamSide


def _team_side_to_str(side: TeamSide) -> str:
    return str(side.value)


def _str_to_team_side(s: str) -> TeamSide:
    return TeamSide(int(s))


def _game_status_to_str(status: GameStatus) -> str:
    return status.value


def _str_to_game_status(s: str) -> GameStatus:
    return GameStatus(s)


def _row_to_player(row: sqlite3.Row) -> Player:
    items: list[int] = json.loads(row["items"]) if row["items"] else []
    return Player(
        puuid=row["puuid"],
        summoner_name=row["summoner_name"],
        champion_id=row["champion_id"],
        champion_name=row["champion_name"],
        team=_str_to_team_side(row["side"]),
        role=row["role"],
        rank=row["rank"],
        kills=row["kills"],
        deaths=row["deaths"],
        assists=row["assists"],
        cs=row["cs"],
        gold=row["gold"],
        damage_to_champions=row["damage"],
        vision_score=row["vision_score"],
        items=items,
        level=row["level"],
    )


def init_db(db_path: str = "tracker.db") -> sqlite3.Connection:
    """Crée les tables si elles n'existent pas et retourne la connexion.

    Args:
        db_path: Chemin vers le fichier SQLite. ``":memory:"`` pour une
            base en mémoire.

    Returns:
        Instance ``sqlite3.Connection`` avec ``row_factory`` configuré.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS games (
            game_id         INTEGER PRIMARY KEY,
            match_id        TEXT,
            status          TEXT    NOT NULL DEFAULT 'pending',
            game_mode       TEXT    NOT NULL DEFAULT '',
            game_duration   INTEGER NOT NULL DEFAULT 0,
            team1_id        INTEGER NOT NULL DEFAULT 0,
            team1_side      TEXT    NOT NULL DEFAULT '100',
            team2_id        INTEGER NOT NULL DEFAULT 0,
            team2_side      TEXT    NOT NULL DEFAULT '200',
            tracked_puuid   TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS players (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id         INTEGER NOT NULL REFERENCES games(game_id),
            puuid           TEXT    NOT NULL,
            summoner_name   TEXT    NOT NULL DEFAULT '',
            champion_id     INTEGER NOT NULL DEFAULT 0,
            champion_name   TEXT    NOT NULL DEFAULT '',
            team_id         INTEGER NOT NULL DEFAULT 0,
            side            TEXT    NOT NULL DEFAULT '100',
            role            TEXT,
            rank            TEXT,
            kills           INTEGER NOT NULL DEFAULT 0,
            deaths          INTEGER NOT NULL DEFAULT 0,
            assists         INTEGER NOT NULL DEFAULT 0,
            cs              INTEGER NOT NULL DEFAULT 0,
            gold            INTEGER NOT NULL DEFAULT 0,
            damage          INTEGER NOT NULL DEFAULT 0,
            vision_score    INTEGER NOT NULL DEFAULT 0,
            items           TEXT    NOT NULL DEFAULT '[]',
            level           INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
        CREATE INDEX IF NOT EXISTS idx_games_match_id ON games(match_id);
        CREATE INDEX IF NOT EXISTS idx_players_game_id ON players(game_id);
        CREATE INDEX IF NOT EXISTS idx_players_puuid ON players(puuid);
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Sauvegarde
# ---------------------------------------------------------------------------

def _save_game_row(conn: sqlite3.Connection, game: Game) -> None:
    """Insère ou met à jour la ligne principale de la game."""
    teams = game.teams
    t1 = teams[0] if len(teams) > 0 else None
    t2 = teams[1] if len(teams) > 1 else None

    now = datetime.utcnow().isoformat()

    conn.execute(
        """
        INSERT OR REPLACE INTO games (
            game_id, match_id, status, game_mode, game_duration,
            team1_id, team1_side, team2_id, team2_side,
            tracked_puuid, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game.game_id,
            game.match_id,
            _game_status_to_str(game.status),
            game.game_mode,
            game.game_duration,
            t1.team_id if t1 else 0,
            _team_side_to_str(t1.side) if t1 else "100",
            t2.team_id if t2 else 0,
            _team_side_to_str(t2.side) if t2 else "200",
            game.tracked_player_puuid,
            game.created_at.isoformat(),
            now,
        ),
    )


def _save_players(conn: sqlite3.Connection, game: Game) -> None:
    """Supprime les anciens players puis insère les nouveaux."""
    conn.execute("DELETE FROM players WHERE game_id = ?", (game.game_id,))

    for team in game.teams:
        for player in team.players:
            conn.execute(
                """
                INSERT INTO players (
                    game_id, puuid, summoner_name, champion_id, champion_name,
                    team_id, side, role, rank,
                    kills, deaths, assists, cs, gold, damage,
                    vision_score, items, level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    game.game_id,
                    player.puuid,
                    player.summoner_name,
                    player.champion_id,
                    player.champion_name,
                    team.team_id,
                    _team_side_to_str(player.team),
                    player.role,
                    player.rank,
                    player.kills,
                    player.deaths,
                    player.assists,
                    player.cs,
                    player.gold,
                    player.damage_to_champions,
                    player.vision_score,
                    json.dumps(player.items),
                    player.level,
                ),
            )


def save_game(conn: sqlite3.Connection, game: Game) -> None:
    """Insère ou met à jour une Game et tous ses Players associés.

    Args:
        conn: Connexion SQLite (obtenue via :func:`init_db`).
        game: Objet :class:`Game` à persister.
    """
    _save_game_row(conn, game)
    _save_players(conn, game)
    conn.commit()


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def _load_players_for_game(conn: sqlite3.Connection, game_id: int) -> list[Player]:
    rows = conn.execute(
        "SELECT * FROM players WHERE game_id = ?", (game_id,)
    ).fetchall()
    return [_row_to_player(r) for r in rows]


def _build_game(row: sqlite3.Row, players: list[Player]) -> Game:
    teams_map: dict[int, list[Player]] = {}
    for p in players:
        team_id = p.team.value  # TeamSide enum value → 100 or 200
        teams_map.setdefault(team_id, []).append(p)

    teams: list[Team] = []
    for team_id, team_players in sorted(teams_map.items()):
        teams.append(
            Team(
                team_id=team_id,
                side=_str_to_team_side(str(team_id)),
                players=team_players,
            )
        )

    return Game(
        game_id=row["game_id"],
        match_id=row["match_id"],
        status=_str_to_game_status(row["status"]),
        game_mode=row["game_mode"],
        game_duration=row["game_duration"],
        teams=teams,
        tracked_player_puuid=row["tracked_puuid"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def get_game_by_id(conn: sqlite3.Connection, game_id: int) -> Game | None:
    """Récupère une Game par son ``game_id``.

    Args:
        conn: Connexion SQLite.
        game_id: Identifiant Riot de la game.

    Returns:
        Objet :class:`Game` complet ou ``None`` si introuvable.
    """
    row = conn.execute(
        "SELECT * FROM games WHERE game_id = ?", (game_id,)
    ).fetchone()
    if row is None:
        return None
    players = _load_players_for_game(conn, game_id)
    return _build_game(row, players)


def get_game_by_match_id(conn: sqlite3.Connection, match_id: str) -> Game | None:
    """Récupère une Game par son ``match_id``.

    Args:
        conn: Connexion SQLite.
        match_id: Identifiant Riot du match (format ``EUW1_123456``).

    Returns:
        Objet :class:`Game` complet ou ``None`` si introuvable.
    """
    row = conn.execute(
        "SELECT * FROM games WHERE match_id = ?", (match_id,)
    ).fetchone()
    if row is None:
        return None
    players = _load_players_for_game(conn, row["game_id"])
    return _build_game(row, players)


def _get_games_by_status(conn: sqlite3.Connection, status: GameStatus) -> list[Game]:
    rows = conn.execute(
        "SELECT * FROM games WHERE status = ?",
        (_game_status_to_str(status),),
    ).fetchall()
    games: list[Game] = []
    for row in rows:
        players = _load_players_for_game(conn, row["game_id"])
        games.append(_build_game(row, players))
    return games


def get_active_games(conn: sqlite3.Connection) -> list[Game]:
    """Récupère toutes les games avec le statut ``IN_PROGRESS``.

    Returns:
        Liste de :class:`Game` en cours.
    """
    return _get_games_by_status(conn, GameStatus.IN_PROGRESS)


def get_pending_games(conn: sqlite3.Connection) -> list[Game]:
    """Récupère toutes les games avec le statut ``PENDING``.

    Returns:
        Liste de :class:`Game` en attente.
    """
    return _get_games_by_status(conn, GameStatus.PENDING)


# ---------------------------------------------------------------------------
# Mise à jour de statut
# ---------------------------------------------------------------------------

def update_game_status(
    conn: sqlite3.Connection, game_id: int, status: GameStatus
) -> None:
    """Met à jour le statut d'une game existante.

    Args:
        conn: Connexion SQLite.
        game_id: Identifiant Riot de la game.
        status: Nouveau statut à appliquer.

    Raises:
        sqlite3.IntegrityError: Si le ``game_id`` n'existe pas.
    """
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE games SET status = ?, updated_at = ? WHERE game_id = ?",
        (_game_status_to_str(status), now, game_id),
    )
    conn.commit()
