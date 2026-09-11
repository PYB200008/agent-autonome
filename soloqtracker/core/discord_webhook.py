"""Agent 4 — Envoi d'embeds Discord via webhook (sans bot)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from core.models import Game, Player, Team, TeamSide

logger = logging.getLogger(__name__)

# ── Couleurs embed ──────────────────────────────────────────────────────────
COLOR_BLUE = 0x3498DB
COLOR_RED = 0xE74C3C
COLOR_VICTORY = 0x2ECC71
COLOR_DEFEAT = 0xE74C3C

# ── Labels ──────────────────────────────────────────────────────────────────
SIDE_LABEL: dict[str, str] = {
    "blue": "\U0001f535 \u00c9quipe Bleue",
    "red": "\U0001f534 \u00c9quipe Rouge",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _format_duration(seconds: int) -> str:
    """Formate une dur\u00e9e en secondes vers ``XXm YYs``."""
    if seconds < 0:
        seconds = 0
    minutes, remaining = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m {remaining:02d}s"
    return f"{minutes}m {remaining:02d}s"


def _fmt(n: int) -> str:
    """Formate un nombre avec s\u00e9parateur de milliers (``1 234 567``)."""
    return f"{n:,}".replace(",", " ")


def _kda(kills: int, deaths: int, assists: int) -> str:
    """Renvoie la cha\u00eene ``K/D/A``."""
    return f"{kills}/{deaths}/{assists}"


def _kda_ratio(kills: int, deaths: int, assists: int) -> float:
    """Calcule le ratio KDA classique (kills + assists) / max(deaths, 1)."""
    return (kills + assists) / max(deaths, 1)


def _cs_per_minute(cs: int, duration_seconds: int) -> float:
    """CS par minute."""
    minutes = max(duration_seconds / 60, 1)
    return cs / minutes


def _gold_per_minute(gold: int, duration_seconds: int) -> float:
    """Or par minute."""
    minutes = max(duration_seconds / 60, 1)
    return gold / minutes


def _side_key(side: TeamSide) -> str:
    """Renvoie ``'blue'`` ou ``'red'`` \u00e0 partir d'un ``TeamSide``."""
    from core.models import TeamSide

    return "blue" if side == TeamSide.BLUE else "red"


# ── Construction des lignes de joueur ───────────────────────────────────────

def _player_line_phase1(player: Player) -> str:
    """Ligne de composition pour un joueur (Phase 1)."""
    champion = player.champion_name or f"Champion {player.champion_id}"
    role = player.role or "?"
    rank = player.rank or "Rang inconnu"
    return f"\u2022 **{champion}** \u2014 {player.summoner_name} ({role}) [{rank}]"


def _player_line_phase2(player: Player, duration: int) -> str:
    """Ligne de r\u00e9sultat pour un joueur (Phase 2)."""
    champion = player.champion_name or f"Champion {player.champion_id}"
    kda = _kda(player.kills, player.deaths, player.assists)
    ratio = _kda_ratio(player.kills, player.deaths, player.assists)
    cspm = _cs_per_minute(player.cs, duration)
    gpm = _gold_per_minute(player.gold, duration)
    return (
        f"\u2022 **{champion}** \u2014 {player.summoner_name}: "
        f"{kda} ({ratio:.1f}) | {player.cs} CS ({cspm:.1f}/min) | "
        f"{_fmt(player.gold)}g ({gpm:.1f}/min) | "
        f"{_fmt(player.damage_to_champions)} DMG | "
        f"Vision {player.vision_score}"
    )


def _team_section(
    team: Team,
    duration: int,
    *,
    phase: int,
    winner_side: TeamSide | None = None,
) -> str:
    """Construit le titre + corps d'une section d'\u00e9quipe."""
    from core.models import TeamSide

    key = _side_key(team.side)
    label = SIDE_LABEL[key]

    if phase == 2 and winner_side is not None:
        if team.side == winner_side:
            label += " \u2014 **Victoire**"
        else:
            label += " \u2014 **D\u00e9faite**"

    lines: list[str] = []
    for p in team.players:
        if phase == 1:
            lines.append(_player_line_phase1(p))
        else:
            lines.append(_player_line_phase2(p, duration))

    return label + "\n" + "\n".join(lines)


def _objectives_line(team: Team) -> str:
    """Ligne d'objectifs d'\u00e9quipe pour l'embed de r\u00e9sultat."""
    return (
        f"Kills {team.kills} | "
        f"Dragons {team.dragons} | "
        f"Barons {team.barons} | "
        f"Tours {team.towers}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Classe principale
# ═══════════════════════════════════════════════════════════════════════════

class DiscordWebhook:
    """Envoie des embeds Discord via un webhook HTTP.

    Le webhook ne fait **aucun** appel API Riot. Il re\u00e7oit des objets
    ``Game`` pr\u00e9-construits via ``send_game_composition`` /
    ``send_game_result``.
    """

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self._client = httpx.AsyncClient(timeout=15.0)

    # ── Fermeture ──────────────────────────────────────────────────────

    async def close(self) -> None:
        """Ferme le client HTTP sous-jacent."""
        await self._client.aclose()

    # ── Envoi g\u00e9n\u00e9rique ─────────────────────────────────────────────

    async def _post_embed(
        self,
        title: str,
        description: str,
        color: int,
        footer_text: str,
    ) -> None:
        """Envoie un unique embed via le webhook Discord.

        G\u00e8re les erreurs HTTP et le rate-limit (429) sans propager d'exception
        pour ne jamais bloquer le pipeline.
        """
        payload = {
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "color": color,
                    "footer": {"text": footer_text},
                }
            ]
        }

        for attempt in range(3):
            try:
                resp = await self._client.post(self.webhook_url, json=payload)
                if resp.status_code == 429:
                    retry_after = float(
                        resp.headers.get("Retry-After", "2")
                    )
                    logger.warning(
                        "Rate-limit Discord (429) \u2014 attente %.1fs", retry_after
                    )
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status_code >= 400:
                    logger.error(
                        "Erreur webhook Discord %s : %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    return
                return
            except httpx.HTTPError as exc:
                logger.error("Erreur HTTP webhook : %s", exc)
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))

    # ═══════════════════════════════════════════════════════════════════
    # Phase 1 \u2014 Embed composition
    # ═══════════════════════════════════════════════════════════════════

    async def send_game_composition(self, game: Game) -> None:
        """Phase 1 : Envoie l'embed de composition de la game en cours.

        L'embed affiche les 10 champions r\u00e9partis par \u00e9quipe, avec les
        r\u00f4les et rangs estim\u00e9s.
        """
        from core.models import TeamSide

        title = f"\U0001f3ae {game.game_mode or 'Partie'} \u2014 Game en cours"

        blue_team: Team | None = None
        red_team: Team | None = None
        for team in game.teams:
            if team.side == TeamSide.BLUE:
                blue_team = team
            elif team.side == TeamSide.RED:
                red_team = team

        sections: list[str] = []
        embed_color = COLOR_BLUE
        for team in (t for t in (blue_team, red_team) if t is not None):
            body = _team_section(team, game.game_duration, phase=1)
            sections.append(body)
            embed_color = COLOR_BLUE if team.side == TeamSide.BLUE else COLOR_RED

        description = "\n\n".join(sections)

        await self._post_embed(title, description, embed_color, "Tracker LoL | Phase 1")
        logger.info("Embed composition envoy\u00e9 pour la game %s", game.game_id)

    # ═══════════════════════════════════════════════════════════════════
    # Phase 2 \u2014 Embed r\u00e9sultat post-game
    # ═══════════════════════════════════════════════════════════════════

    async def send_game_result(self, game: Game) -> None:
        """Phase 2 : Envoie l'embed de r\u00e9sultat avec les stats compl\u00e8tes."""
        from core.models import TeamSide

        duration_str = _format_duration(game.game_duration)
        title = (
            f"\U0001f3c6 R\u00e9sultat \u2014 {game.game_mode or 'Partie'} \u2014 {duration_str}"
        )

        # D\u00e9terminer le vainqueur
        winner_side: TeamSide | None = None
        if len(game.teams) == 2:
            sorted_teams = sorted(game.teams, key=lambda t: t.kills, reverse=True)
            if sorted_teams[0].kills > sorted_teams[1].kills:
                winner_side = sorted_teams[0].side

        # Couleur de l'embed
        embed_color = COLOR_DEFEAT
        for team in game.teams:
            if team.side == winner_side:
                for p in team.players:
                    if p.puuid == game.tracked_player_puuid:
                        embed_color = COLOR_VICTORY
                        break

        blue_team: Team | None = None
        red_team: Team | None = None
        for team in game.teams:
            if team.side == TeamSide.BLUE:
                blue_team = team
            elif team.side == TeamSide.RED:
                red_team = team

        sections: list[str] = []
        for team in (t for t in (blue_team, red_team) if t is not None):
            body = _team_section(team, game.game_duration, phase=2, winner_side=winner_side)
            sections.append(body)

        # Objectifs globaux
        objective_lines: list[str] = []
        for team in (t for t in (blue_team, red_team) if t is not None):
            key = _side_key(team.side)
            emoji = "\U0001f535" if key == "blue" else "\U0001f534"
            objective_lines.append(f"{emoji} {_objectives_line(team)}")

        sections.append("\n".join(objective_lines))

        description = "\n\n".join(sections)

        await self._post_embed(title, description, embed_color, "Tracker LoL | Phase 2")
        logger.info(
            "Embed r\u00e9sultat envoy\u00e9 pour la game %s (match %s)",
            game.game_id,
            game.match_id,
        )
