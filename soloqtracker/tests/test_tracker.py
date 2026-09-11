"""Tests unitaires du tracker LoL — données mockées uniquement.

Aucun appel à l'API Riot réelle : tous les clients HTTP sont factices.
"""

import asyncio
from collections import deque
from datetime import datetime, timezone

import pytest

from core.discord_webhook import (
    DiscordWebhook,
    _format_duration,
    _fmt,
    _kda,
    _kda_ratio,
    _objectives_line,
    _player_line_phase1,
    _player_line_phase2,
)
from agents.match_fetcher import MatchFetcher
from agents.watcher import Watcher
from core import riot_api as riot_api_module
from core.db import (
    get_active_games,
    get_game_by_id,
    get_game_by_match_id,
    get_pending_games,
    init_db,
    save_game,
    update_game_status,
)
from core.models import (
    CHAMPION_TO_ROLE,
    Game,
    GameStatus,
    Player,
    Team,
    TeamSide,
    parse_game_from_match,
    parse_game_from_spectator,
)
from core.riot_api import RiotAPI, RiotAPIError

# ---------------------------------------------------------------------------
# Données mockées communes
# ---------------------------------------------------------------------------

TRACKED_PUUID = "puuid-tracked"
CHAMPION_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def make_spectator_payload(game_id=1234567890, game_mode="CLASSIC"):
    participants = []
    for i in range(10):
        team_id = 100 if i < 5 else 200
        participants.append(
            {
                "puuid": TRACKED_PUUID if i == 0 else f"puuid-{i}",
                "summonerId": f"summoner-{i}",
                "summonerName": f"Player{i}",
                "championId": CHAMPION_IDS[i],
                "teamId": team_id,
                "role": "SOLO" if i < 5 else "DUO",
            }
        )
    return {
        "gameId": game_id,
        "gameMode": game_mode,
        "mapId": 11,
        "gameType": "MATCHED_GAME",
        "gameLength": 392,
        "participants": participants,
    }


def make_match_payload(match_id="EUW1_987654321", game_mode="CLASSIC",
                       game_duration=1832, participants=None, teams=None):
    if participants is None:
        participants = []
        for i in range(10):
            team_id = 100 if i < 5 else 200
            participants.append(
                {
                    "puuid": TRACKED_PUUID if i == 0 else f"puuid-{i}",
                    "summonerName": f"Player{i}",
                    "championId": CHAMPION_IDS[i],
                    "championName": f"Champ{i}",
                    "teamId": team_id,
                    "kills": 10 - i,
                    "deaths": i,
                    "assists": 20 - i,
                    "totalMinionsKilled": 150 + i,
                    "neutralMinionsKilled": 20 + i,
                    "goldEarned": 10000 + i * 100,
                    "totalDamageDealtToChampions": 15000 + i * 500,
                    "visionScore": 25 + i,
                    "item0": 6603 + i,
                    "item1": 3006 + i,
                    "item2": 3074 + i,
                    "item3": 0,
                    "item4": 0,
                    "item5": 0,
                    "item6": 3340 + i,
                    "champLevel": 15 + (i % 3),
                }
            )
    if teams is None:
        teams = [
            {
                "teamId": 100,
                "win": True,
                "objectives": {
                    "kills": {"kills": 30},
                    "deaths": {"kills": 18},
                    "assists": {"kills": 80},
                    "dragon": {"kills": 4},
                    "baron": {"kills": 2},
                    "tower": {"kills": 9},
                },
            },
            {
                "teamId": 200,
                "win": False,
                "objectives": {
                    "kills": {"kills": 18},
                    "deaths": {"kills": 30},
                    "assists": {"kills": 50},
                    "dragon": {"kills": 2},
                    "baron": {"kills": 1},
                    "tower": {"kills": 3},
                },
            },
        ]
    return {
        "metadata": {"matchId": match_id, "dataVersion": "2"},
        "info": {
            "gameMode": game_mode,
            "gameDuration": game_duration,
            "gameCreation": 1750000000000,
            "gameStartTimestamp": 1750000000000,
            "participants": participants,
            "teams": teams,
        },
    }


def make_full_game() -> Game:
    """Game complète pour les tests DB / Discord (stats de fin de partie)."""
    p1 = Player(
        puuid=TRACKED_PUUID, summoner_name="Player0", champion_id=1,
        champion_name="Champ0", team=TeamSide.BLUE, role="top",
        rank="DIAMOND II 37 LP", kills=10, deaths=2, assists=15,
        cs=180, gold=10500, damage_to_champions=18000,
        vision_score=30, items=[6603, 3006, 3074, 3340], level=18,
    )
    p2 = Player(
        puuid="puuid-1", summoner_name="Player1", champion_id=2,
        champion_name="Champ1", team=TeamSide.RED, role="mid",
        kills=3, deaths=9, assists=4, cs=140, gold=6000,
        damage_to_champions=7000, vision_score=12, items=[3006], level=14,
    )
    t1 = Team(team_id=100, side=TeamSide.BLUE, players=[p1],
              kills=30, deaths=18, assists=80, gold=21000, cs=360,
              dragons=4, barons=2, towers=9)
    t2 = Team(team_id=200, side=TeamSide.RED, players=[p2],
              kills=18, deaths=30, assists=50, gold=12000, cs=280,
              dragons=2, barons=1, towers=3)
    return Game(
        game_id=555000,
        match_id="EUW1_987654321",
        status=GameStatus.FINISHED,
        game_mode="CLASSIC",
        game_duration=1832,
        teams=[t1, t2],
        tracked_player_puuid=TRACKED_PUUID,
    )


class FakeRiotClient:
    """Client httpx factice qui compte les appels et renvoie une réponse fixe."""

    def __init__(self, responses, close_calls=True):
        self.responses = list(responses)
        self.calls = 0
        self.closed = 0
        self.close_calls = close_calls

    async def request(self, method, url, params=None):
        self.calls += 1
        resp = self.responses[0] if len(self.responses) == 1 else self.responses.pop(0)
        return resp

    async def aclose(self):
        self.closed += 1


class FakeResponse:
    def __init__(self, status_code, json_data=None, text="", reason_phrase=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text or reason_phrase
        self.reason_phrase = reason_phrase

    def json(self):
        return self._json


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_conn():
    conn = init_db(":memory:")
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. core/models.py
# ---------------------------------------------------------------------------

class TestParseGameFromSpectator:
    def test_structure_teams_players(self):
        game = parse_game_from_spectator(make_spectator_payload(), TRACKED_PUUID)
        assert game.game_id == 1234567890
        assert game.game_mode == "CLASSIC"
        assert game.status is GameStatus.IN_PROGRESS
        assert game.tracked_player_puuid == TRACKED_PUUID
        assert len(game.teams) == 2
        total = sum(len(t.players) for t in game.teams)
        assert total == 10

    def test_team_id_mapping(self):
        game = parse_game_from_spectator(make_spectator_payload(), TRACKED_PUUID)
        sides = {t.side for t in game.teams}
        assert sides == {TeamSide.BLUE, TeamSide.RED}
        blue = next(t for t in game.teams if t.side is TeamSide.BLUE)
        red = next(t for t in game.teams if t.side is TeamSide.RED)
        assert blue.team_id == 100
        assert red.team_id == 200
        assert all(p.team is TeamSide.BLUE for p in blue.players)
        assert all(p.team is TeamSide.RED for p in red.players)
        assert len(blue.players) == 5
        assert len(red.players) == 5

    def test_player_fields(self):
        game = parse_game_from_spectator(make_spectator_payload(), TRACKED_PUUID)
        first = game.teams[0].players[0]
        assert first.champion_id == CHAMPION_IDS[0]
        assert first.puuid == TRACKED_PUUID
        assert first.summoner_name == "Player0"
        assert first.role == CHAMPION_TO_ROLE.get(CHAMPION_IDS[0])


class TestParseGameFromMatch:
    def test_stats_complete(self):
        game = parse_game_from_match(make_match_payload(), TRACKED_PUUID)
        assert game.match_id == "EUW1_987654321"
        assert game.game_mode == "CLASSIC"
        assert game.game_duration == 1832
        assert game.status is GameStatus.FINISHED
        assert len(game.teams) == 2
        assert sum(len(t.players) for t in game.teams) == 10

        player = next(
            p for t in game.teams for p in t.players
            if p.puuid == TRACKED_PUUID
        )
        assert player.kills == 10
        assert player.deaths == 0
        assert player.assists == 20
        assert player.cs == 150 + 20  # minions + neutres
        assert player.gold == 10000
        assert player.damage_to_champions == 15000
        assert player.vision_score == 25

    def test_items_include_non_zero(self):
        game = parse_game_from_match(make_match_payload(), TRACKED_PUUID)
        player = next(
            p for t in game.teams for p in t.players
            if p.puuid == TRACKED_PUUID
        )
        # item0/1/2 et item6 non nuls ; item3/4/5 = 0 filtrés
        assert player.items == [6603, 3006, 3074, 3340]

    def test_team_objectives(self):
        game = parse_game_from_match(make_match_payload(), TRACKED_PUUID)
        blue = next(t for t in game.teams if t.side is TeamSide.BLUE)
        red = next(t for t in game.teams if t.side is TeamSide.RED)
        assert blue.dragons == 4
        assert blue.barons == 2
        assert blue.towers == 9
        assert red.dragons == 2
        assert red.barons == 1
        assert red.towers == 3

    def test_team_id_mapping(self):
        game = parse_game_from_match(make_match_payload(), TRACKED_PUUID)
        sides = {t.side for t in game.teams}
        assert sides == {TeamSide.BLUE, TeamSide.RED}
        assert all(p.team is TeamSide.BLUE for t in game.teams for p in t.players
                   if t.side is TeamSide.BLUE)


# ---------------------------------------------------------------------------
# 2. core/db.py
# ---------------------------------------------------------------------------

class TestDb:
    def test_init_db_creates_tables(self, db_conn):
        tables = {
            r["name"]
            for r in db_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"games", "players"} <= tables

    def test_save_get_round_trip(self, db_conn):
        game = make_full_game()
        save_game(db_conn, game)

        loaded = get_game_by_id(db_conn, game.game_id)
        assert loaded is not None
        assert loaded.game_id == game.game_id
        assert loaded.match_id == game.match_id
        assert loaded.status is game.status
        assert loaded.game_mode == game.game_mode
        assert loaded.game_duration == game.game_duration
        assert loaded.tracked_player_puuid == TRACKED_PUUID
        assert len(loaded.teams) == 2

        stored = {p.puuid: p for t in loaded.teams for p in t.players}
        assert set(stored) == {TRACKED_PUUID, "puuid-1"}
        p = stored[TRACKED_PUUID]
        assert p.summoner_name == "Player0"
        assert p.champion_id == 1
        assert p.champion_name == "Champ0"
        assert p.team is TeamSide.BLUE
        assert p.role == "top"
        assert p.rank == "DIAMOND II 37 LP"
        assert p.kills == 10
        assert p.deaths == 2
        assert p.assists == 15
        assert p.cs == 180
        assert p.gold == 10500
        assert p.damage_to_champions == 18000
        assert p.vision_score == 30
        assert p.items == [6603, 3006, 3074, 3340]
        assert p.level == 18

    def test_update_game_status(self, db_conn):
        game = make_full_game()
        game.status = GameStatus.IN_PROGRESS
        save_game(db_conn, game)

        update_game_status(db_conn, game.game_id, GameStatus.FINISHED)
        loaded = get_game_by_id(db_conn, game.game_id)
        assert loaded.status is GameStatus.FINISHED

    def test_get_by_match_id_and_status(self, db_conn):
        in_progress = make_full_game()
        in_progress.game_id = 700001
        in_progress.status = GameStatus.IN_PROGRESS
        save_game(db_conn, in_progress)

        pending = make_full_game()
        pending.game_id = 700002
        pending.status = GameStatus.PENDING
        save_game(db_conn, pending)

        assert get_game_by_match_id(db_conn, "EUW1_987654321").game_id == 700001
        assert [g.game_id for g in get_active_games(db_conn)] == [700001]
        assert [g.game_id for g in get_pending_games(db_conn)] == [700002]

    def test_get_missing_game_returns_none(self, db_conn):
        assert get_game_by_id(db_conn, 999999) is None


# ---------------------------------------------------------------------------
# 3. core/riot_api.py — rate limit & retry (aucun appel réseau réel)
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def _api(self, monkeypatch, timestamps):
        api = RiotAPI("test-key", "euw1")
        api._timestamps = deque(timestamps, maxlen=100)
        clock = {"t": 100.0}
        sleeps = []

        monkeypatch.setattr(riot_api_module.time, "monotonic",
                            lambda: clock["t"])

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            clock["t"] += seconds

        monkeypatch.setattr(riot_api_module.asyncio, "sleep", fake_sleep)
        return api, sleeps

    def test_no_wait_below_limits(self, monkeypatch):
        api, sleeps = self._api(monkeypatch, [100.0] * 5)
        asyncio.run(api._wait_if_needed())
        assert sleeps == []

    def test_wait_when_20_in_same_second(self, monkeypatch):
        api, sleeps = self._api(monkeypatch, [100.0] * 20)
        asyncio.run(api._wait_if_needed())
        assert sleeps, "une attente devait être déclenchée"
        assert sum(sleeps) >= 1.0  # attend que la fenêtre de 1s soit passée

    def test_wait_at_2min_window(self, monkeypatch):
        api, sleeps = self._api(monkeypatch, [100.0] * 100)
        asyncio.run(api._wait_if_needed())
        assert sleeps
        assert abs(sleeps[0] - 120.0) < 1e-6


class TestRetry:
    def _retry_api(self, monkeypatch, attempts=3):
        api = RiotAPI("test-key", "euw1")
        api._client = FakeRiotClient([
            FakeResponse(429, text="rate limited", reason_phrase="Too Many Requests")
        ])
        retry_obj = RiotAPI._send.retry
        monkeypatch.setattr(retry_obj, "stop", __import__(
            "tenacity").stop_after_attempt(attempts))
        monkeypatch.setattr(retry_obj, "wait", __import__(
            "tenacity").wait_none())
        return api

    def test_retry_on_429_then_raise(self, monkeypatch):
        api = self._retry_api(monkeypatch, attempts=3)
        with pytest.raises(RiotAPIError):
            asyncio.run(api._request("GET", "http://riot.local/match"))
        assert api._client.calls == 3

    def test_retry_survives_then_succeeds(self, monkeypatch):
        api = RiotAPI("test-key", "euw1")
        api._client = FakeRiotClient([
            FakeResponse(500, text="boom", reason_phrase="Server Error"),
            FakeResponse(200, json_data={"ok": 1}),
        ])
        retry_obj = RiotAPI._send.retry
        monkeypatch.setattr(retry_obj, "stop", __import__(
            "tenacity").stop_after_attempt(2))
        monkeypatch.setattr(retry_obj, "wait", __import__(
            "tenacity").wait_none())
        result = asyncio.run(api._request("GET", "http://riot.local/match"))
        assert result == {"ok": 1}
        assert api._client.calls == 2

    def test_5xx_then_raise_rriot_error(self, monkeypatch):
        api = self._retry_api(monkeypatch, attempts=2)
        api._client = FakeRiotClient([FakeResponse(
            503, text="unavailable", reason_phrase="Service Unavailable")])
        with pytest.raises(RiotAPIError) as excinfo:
            asyncio.run(api._request("GET", "http://riot.local/match"))
        assert excinfo.value.status_code == 503


class TestRequestBehavior:
    def test_request_returns_json(self):
        api = RiotAPI("test-key", "euw1")
        api._client = FakeRiotClient([FakeResponse(
            200, json_data={"gameId": 42})])
        assert asyncio.run(
            api._request("GET", "http://riot.local/x")) == {"gameId": 42}

    def test_404_not_found_ok_returns_none(self):
        api = RiotAPI("test-key", "euw1")
        api._client = FakeRiotClient([FakeResponse(404, reason_phrase="Not Found")])
        assert asyncio.run(
            api._request("GET", "http://riot.local/x", not_found_ok=True)) is None

    def test_4xx_raises(self):
        api = RiotAPI("test-key", "euw1")
        api._client = FakeRiotClient([FakeResponse(403, reason_phrase="Forbidden")])
        with pytest.raises(RiotAPIError) as excinfo:
            asyncio.run(api._request("GET", "http://riot.local/x"))
        assert excinfo.value.status_code == 403


# ---------------------------------------------------------------------------
# 4. agents/watcher.py
# ---------------------------------------------------------------------------

class FakeSpectatorAPI:
    """Fake RiotAPI pour le Watcher."""

    def __init__(self, active_game, league_entries=None):
        self.active_game = active_game
        self.league_entries = league_entries or [{
            "queueType": "RANKED_SOLO_5x5",
            "tier": "DIAMOND",
            "rank": "II",
            "leaguePoints": 37,
        }]
        self.calls = {"active": 0, "summoner": 0, "league": 0}

    async def get_active_game(self, summoner_id):
        self.calls["active"] += 1
        return self.active_game

    async def get_summoner_by_puuid(self, puuid):
        self.calls["summoner"] += 1
        return {"id": f"summoner::{puuid}"}

    async def get_league_entries(self, summoner_id):
        self.calls["league"] += 1
        return self.league_entries


class TestWatcher:
    def test_detects_game_and_notifies(self, db_conn):
        api = FakeSpectatorAPI(make_spectator_payload())
        notified = []

        async def callback(game):
            notified.append(game)

        watcher = Watcher(
            api, db_conn, [TRACKED_PUUID],
            poll_interval=1, callback=callback,
        )
        result = asyncio.run(watcher._check_puuid(TRACKED_PUUID, set()))
        assert result.detected is True
        assert result.game_id == 1234567890

        assert len(notified) == 1
        game = notified[0]
        assert game.game_id == 1234567890
        assert game.status is GameStatus.IN_PROGRESS
        assert len(game.teams) == 2

        saved = get_game_by_id(db_conn, 1234567890)
        assert saved is not None
        assert saved.game_mode == "CLASSIC"
        assert len(saved.teams) == 2
        ranks = {p.rank for t in saved.teams for p in t.players}
        assert ranks == {"DIAMOND II 37 LP"}

    def test_no_game_no_callback(self, db_conn, monkeypatch):
        api = FakeSpectatorAPI(None)
        notified = []

        async def callback(game):
            notified.append(game)

        watcher = Watcher(api, db_conn, [TRACKED_PUUID], callback=callback)
        result = asyncio.run(watcher._check_puuid(TRACKED_PUUID, set()))
        assert result.detected is False
        assert notified == []
        assert get_game_by_id(db_conn, 1234567890) is None

    def test_already_tracked_game_ignored(self, db_conn):
        save_game(db_conn, parse_game_from_spectator(
            make_spectator_payload(), TRACKED_PUUID))
        api = FakeSpectatorAPI(make_spectator_payload())
        notified = []

        async def callback(game):
            notified.append(game)

        watcher = Watcher(api, db_conn, [TRACKED_PUUID], callback=callback)
        result = asyncio.run(watcher._check_puuid(TRACKED_PUUID, {1234567890}))
        assert result.detected is False
        assert notified == []


# ---------------------------------------------------------------------------
# 5. agents/match_fetcher.py
# ---------------------------------------------------------------------------

class FakeMatchAPI:
    def __init__(self, history, match_data):
        self.history = history
        self.match_data = match_data
        self.calls = {"history": 0, "match": 0}

    async def get_match_history(self, puuid, count=5):
        self.calls["history"] += 1
        return self.history

    async def get_match(self, match_id):
        self.calls["match"] += 1
        return self.match_data


class TestMatchFetcher:
    def _plant_in_progress_game(self, db_conn):
        game_id = 999111
        player = Player(
            puuid=TRACKED_PUUID, summoner_name="Player0", champion_id=1,
            champion_name="Champ0", team=TeamSide.BLUE,
        )
        t1 = Team(team_id=100, side=TeamSide.BLUE, players=[player])
        game = Game(
            game_id=game_id, status=GameStatus.IN_PROGRESS,
            game_mode="CLASSIC", teams=[t1],
            tracked_player_puuid=TRACKED_PUUID,
            created_at=datetime.utcnow(),
        )
        save_game(db_conn, game)
        return game

    def test_detects_finish_and_finalizes(self, db_conn):
        game = self._plant_in_progress_game(db_conn)
        match_id = "EUW1_555000"
        payload = make_match_payload(match_id=match_id)
        info = payload["info"]
        info["gameMode"] = game.game_mode
        created_utc = game.created_at.replace(tzinfo=timezone.utc)
        info["gameCreation"] = int(created_utc.timestamp() * 1000)

        api = FakeMatchAPI([match_id], payload)
        finished = []

        async def callback(finalized):
            finished.append(finalized)

        fetcher = MatchFetcher(api, db_conn, poll_interval=1, callback=callback)
        asyncio.run(fetcher._check_active_games())

        assert len(finished) == 1
        final = finished[0]
        assert final.match_id == match_id
        assert final.game_id == game.game_id
        assert final.status is GameStatus.FINISHED
        assert final.game_duration == 1832

        saved = get_game_by_id(db_conn, game.game_id)
        assert saved.status is GameStatus.FINISHED
        assert saved.match_id == match_id
        assert get_active_games(db_conn) == []

        assert api.calls["history"] == 1
        assert api.calls["match"] == 1

    def test_still_in_progress_no_finish(self, db_conn):
        game = self._plant_in_progress_game(db_conn)
        api = FakeMatchAPI([], None)
        finished = []

        async def callback(finalized):
            finished.append(finalized)

        fetcher = MatchFetcher(api, db_conn, callback=callback)
        asyncio.run(fetcher._check_active_games())
        assert finished == []
        assert get_active_games(db_conn)[0].status is GameStatus.IN_PROGRESS


# ---------------------------------------------------------------------------
# 6. core/discord_webhook.py — formatage & envoy d'embeds (sans connexion)
# ---------------------------------------------------------------------------

class TestDiscordFormatting:
    def test_duration_formatting(self):
        assert _format_duration(0) == "0m 00s"
        assert _format_duration(59) == "0m 59s"
        assert _format_duration(60) == "1m 00s"
        assert _format_duration(1832) == "30m 32s"
        assert _format_duration(3661) == "1h 01m 01s"
        assert _format_duration(-5) == "0m 00s"

    def test_number_formatting(self):
        assert _fmt(0) == "0"
        assert _fmt(1234) == "1 234"
        assert _fmt(1234567) == "1 234 567"

    def test_kda(self):
        assert _kda(2, 3, 4) == "2/3/4"
        assert _kda_ratio(10, 0, 5) == 15.0  # deaths=0 → max(0,1)=1
        assert _kda_ratio(2, 2, 4) == 3.0

    def test_player_lines(self):
        p = Player(
            puuid="x", summoner_name="Nunu", champion_id=20,
            champion_name="Nunu", team=TeamSide.BLUE, role="jungle",
            rank="GOLD 3 25 LP", kills=5, deaths=2, assists=8, cs=180,
            gold=12000, damage_to_champions=15000, vision_score=25,
        )
        line1 = _player_line_phase1(p)
        assert "Nunu" in line1 and "jungle" in line1 and "GOLD 3 25 LP" in line1

        line2 = _player_line_phase2(p, 1800)
        assert "5/2/8" in line2
        assert "180 CS" in line2
        assert "12 000g" in line2
        assert "15 000 DMG" in line2
        assert "Vision 25" in line2

    def test_objectives_line(self):
        team = make_full_game().teams[0]
        line = _objectives_line(team)
        assert "Kills 30" in line
        assert "Dragons 4" in line
        assert "Barons 2" in line
        assert "Tours 9" in line


class TestDiscordEmbeds:
    def _make_webhook(self, monkeypatch):
        webhook = DiscordWebhook("https://discord.com/api/webhooks/test/test")
        captured = []

        class _FakeResponse:
            status_code = 200
            headers = {}
            text = ""

        async def fake_post(url, json=None):
            captured.append(json)
            return _FakeResponse

        monkeypatch.setattr(webhook._client, "post", fake_post)
        return webhook, captured

    def _close(self, webhook):
        asyncio.run(webhook.close())

    def test_send_game_composition(self, monkeypatch):
        game = parse_game_from_spectator(make_spectator_payload(), TRACKED_PUUID)
        webhook, captured = self._make_webhook(monkeypatch)
        asyncio.run(webhook.send_game_composition(game))
        self._close(webhook)
        assert len(captured) == 1
        embed = captured[0]["embeds"][0]
        assert "Game en cours" in embed["title"]
        assert "Player0" in embed["description"]
        assert "Bleue" in embed["description"] or "Equipe" in embed["description"]
        assert "Tracker LoL" in embed["footer"]["text"]

    def test_send_game_result(self, monkeypatch):
        game = make_full_game()
        webhook, captured = self._make_webhook(monkeypatch)
        asyncio.run(webhook.send_game_result(game))
        self._close(webhook)
        assert len(captured) == 1
        embed = captured[0]["embeds"][0]
        assert "Résultat" in embed["title"]
        assert "10/2/15" in embed["description"]
        assert "Dragons 4" in embed["description"]
        assert "Kills 30" in embed["description"]
        assert "Tracker LoL" in embed["footer"]["text"]

    def test_no_champion_name_uses_id(self, monkeypatch):
        payload = make_spectator_payload()
        for p in payload["participants"]:
            p["championName"] = ""
        game = parse_game_from_spectator(payload, TRACKED_PUUID)
        webhook, captured = self._make_webhook(monkeypatch)
        asyncio.run(webhook.send_game_composition(game))
        self._close(webhook)
        embed = captured[0]["embeds"][0]
        assert "Champion" in embed["description"]

    def test_rate_limit_429_retries(self, monkeypatch):
        webhook = DiscordWebhook("https://discord.com/api/webhooks/test/test")
        calls = {"n": 0}

        class _Fake429:
            status_code = 429
            headers = {"Retry-After": "0"}
            text = ""

        class _FakeOK:
            status_code = 200
            headers = {}
            text = ""

        async def fake_post(url, json=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return _Fake429
            return _FakeOK

        monkeypatch.setattr(webhook._client, "post", fake_post)
        game = make_full_game()
        asyncio.run(webhook.send_game_result(game))
        self._close(webhook)
        assert calls["n"] == 2

    def test_http_error_silently_ignored(self, monkeypatch):
        webhook = DiscordWebhook("https://discord.com/api/webhooks/test/test")

        class _Fake500:
            status_code = 500
            headers = {}
            text = "oups"

        async def fake_post(url, json=None):
            return _Fake500

        monkeypatch.setattr(webhook._client, "post", fake_post)
        game = make_full_game()
        assert asyncio.run(webhook.send_game_result(game)) is None
        self._close(webhook)


# ---------------------------------------------------------------------------
# 7. Interopérabilité : imports main.py / config.py + paires watcher/fetcher
# ---------------------------------------------------------------------------

class TestImports:
    def test_main_imports(self):
        import config
        import main
        assert hasattr(main, "main")
        assert hasattr(config, "load_config")

    def test_config_load_ok(self, monkeypatch):
        monkeypatch.setenv("RIOT_API_KEY", "dummy-key")
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/test")
        monkeypatch.setenv("TRACKED_PUUIDS", "puuid-a, puuid-b, ")
        monkeypatch.setenv("WATCHER_INTERVAL", "42")
        import config
        cfg = config.load_config()
        assert cfg.riot_api_key == "dummy-key"
        assert cfg.discord_webhook_url == "https://discord.com/api/webhooks/test/test"
        assert cfg.tracked_puuids == ["puuid-a", "puuid-b"]
        assert cfg.watcher_interval == 42

    def test_config_missing_env_raises(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "load_dotenv", lambda: None)
        monkeypatch.delenv("RIOT_API_KEY", raising=False)
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        with pytest.raises(config.ConfigError):
            config.load_config()

    def test_watcher_to_matchfetcher_data_flow(self, db_conn, monkeypatch):
        """Watcher détecte une game, MatchFetcher la finalise : enchaînement."""
        spectator_api = FakeSpectatorAPI(make_spectator_payload())
        watcher = Watcher(spectator_api, db_conn, [TRACKED_PUUID])
        result = asyncio.run(watcher._check_puuid(TRACKED_PUUID, set()))
        assert result.detected is True

        saved = get_game_by_id(db_conn, 1234567890)
        assert saved is not None
        assert saved.tracked_player_puuid == TRACKED_PUUID

        match_id = "EUW1_WATCHED"
        payload = make_match_payload(match_id=match_id)
        created_utc = saved.created_at.replace(tzinfo=timezone.utc)
        payload["info"]["gameCreation"] = int(created_utc.timestamp() * 1000)
        match_api = FakeMatchAPI([match_id], payload)
        fetcher = MatchFetcher(match_api, db_conn, poll_interval=1)
        asyncio.run(fetcher._check_active_games())

        final = get_game_by_id(db_conn, 1234567890)
        assert final.status is GameStatus.FINISHED
        assert final.match_id == match_id
        assert {p.puuid for t in final.teams for p in t.players} == {
            TRACKED_PUUID, *[f"puuid-{i}" for i in range(1, 10)],
        }