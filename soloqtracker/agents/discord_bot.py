"""Agent 4 — Bot Discord publant les embeds de suivi de partie LoL."""

import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from core.models import Game, Player, Team, TeamSide

logger = logging.getLogger(__name__)

# ── Couleurs embed ──────────────────────────────────────────────────────────
COLOR_BLUE = discord.Color.blue()
COLOR_RED = discord.Color.red()
COLOR_VICTORY = discord.Color.green()
COLOR_DEFEAT = discord.Color.red()

# ── Emojis / labels ─────────────────────────────────────────────────────────
SIDE_LABEL: dict[str, str] = {
    "blue": "🔵 Équipe Bleue",
    "red": "🔴 Équipe Rouge",
}
SIDE_COLOR: dict[str, discord.Color] = {
    "blue": COLOR_BLUE,
    "red": COLOR_RED,
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _format_duration(seconds: int) -> str:
    """Formate une durée en secondes vers ``XXm YYs``."""
    if seconds < 0:
        seconds = 0
    minutes, remaining = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m {remaining:02d}s"
    return f"{minutes}m {remaining:02d}s"


def _fmt(n: int) -> str:
    """Formate un nombre avec séparateur de milliers (``1 234 567``)."""
    return f"{n:,}".replace(",", " ")


def _kda(kills: int, deaths: int, assists: int) -> str:
    """Renvoie la chaîne ``K/D/A``."""
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


def _side_key(side: "TeamSide") -> str:
    """Renvoie ``'blue'`` ou ``'red'`` à partir d'un ``TeamSide``."""
    from core.models import TeamSide

    return "blue" if side == TeamSide.BLUE else "red"


# ── Construction des lignes de joueur ───────────────────────────────────────

def _player_line_phase1(player: "Player") -> str:
    """Ligne de composition pour un joueur (Phase 1)."""
    champion = player.champion_name or f"Champion#{player.champion_id}"
    role = player.role or "?"
    rank = player.rank or "Rang inconnu"
    return f"• **{champion}** — {player.summoner_name} ({role}) [{rank}]"


def _player_line_phase2(player: "Player", duration: int) -> str:
    """Ligne de résultat pour un joueur (Phase 2)."""
    champion = player.champion_name or f"Champion#{player.champion_id}"
    kda = _kda(player.kills, player.deaths, player.assists)
    ratio = _kda_ratio(player.kills, player.deaths, player.assists)
    cspm = _cs_per_minute(player.cs, duration)
    gpm = _gold_per_minute(player.gold, duration)
    return (
        f"• **{champion}** — {player.summoner_name}: "
        f"{kda} ({ratio:.1f}) | {player.cs} CS ({cspm:.1f}/min) | "
        f"{_fmt(player.gold)}g ({gpm:.1f}/min) | "
        f"{_fmt(player.damage_to_champions)} DMG | "
        f"Vision {player.vision_score}"
    )


def _team_section(
    team: "Team",
    duration: int,
    *,
    phase: int,
    winner_side: "TeamSide | None" = None,
) -> tuple[str, discord.Color]:
    """Construit le titre + corps d'une section d'équipe et sa couleur."""
    from core.models import TeamSide

    key = _side_key(team.side)
    label = SIDE_LABEL[key]
    color = SIDE_COLOR[key]

    if phase == 2 and winner_side is not None:
        if team.side == winner_side:
            label += " — **Victoire**"
        else:
            label += " — **Défaite**"

    lines: list[str] = []
    for p in team.players:
        if phase == 1:
            lines.append(_player_line_phase1(p))
        else:
            lines.append(_player_line_phase2(p, duration))

    return label + "\n" + "\n".join(lines), color


def _objectives_line(team: "Team") -> str:
    """Ligne d'objectifs d'équipe pour l'embed de résultat."""
    return (
        f"Kills {team.kills} | "
        f"Dragons {team.dragons} | "
        f"Barons {team.barons} | "
        f"Tours {team.towers}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Classe principale
# ═══════════════════════════════════════════════════════════════════════════

class DiscordBot:
    """Bot Discord qui publie les embeds de suivi de parties LoL.

    Le bot ne fait **aucun** appel API Riot. Il reçoit des objets ``Game``
    pré-construits via ``send_game_composition`` / ``send_game_result``.
    """

    def __init__(self, token: str, channel_id: int) -> None:
        self.token = token
        self.channel_id = channel_id

        intents = discord.Intents.default()
        self.bot = commands.Bot(command_prefix="!", intents=intents)

        self._setup_events()

    # ── Configuration des events / commandes ────────────────────────────

    def _setup_events(self) -> None:
        """Configure les events et commandes du bot."""

        @self.bot.event
        async def on_ready() -> None:
            logger.info("Bot connecté en tant que %s", self.bot.user)

        @self.bot.command(name="tracker")
        async def tracker_command(ctx: commands.Context) -> None:  # type: ignore[override]
            """Commande ``!tracker`` — vérifie que le bot est en vie."""
            await ctx.send("Tracker LoL opérationnel !")

    # ── Cycle de vie ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Démarre le bot (bloque jusqu'à l'arrêt)."""
        await self.bot.start(self.token)

    async def stop(self) -> None:
        """Arrête proprement le bot."""
        await self.bot.close()

    def run(self) -> None:
        """Point d'entrée bloquant (wrapper de ``bot.run``)."""
        self.bot.run(self.token)

    # ── Helpers channel ─────────────────────────────────────────────────

    def _get_channel(self) -> discord.TextChannel | None:
        """Renvoie le channel cible, ou ``None`` si introuvable."""
        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            logger.error("Channel %s introuvable", self.channel_id)
        return channel if isinstance(channel, discord.TextChannel) else None

    # ═══════════════════════════════════════════════════════════════════
    # Phase 1 — Embed composition
    # ═══════════════════════════════════════════════════════════════════

    async def send_game_composition(self, game: "Game") -> None:
        """Phase 1 : Envoie l'embed de composition de la game en cours.

        L'embed affiche les 10 champions répartis par équipe, avec les
        rôles et rangs estimés.
        """
        channel = self._get_channel()
        if channel is None:
            return

        from core.models import TeamSide

        title = f"🎮 {game.game_mode or 'Partie'} — Game en cours"

        # Trier les équipes : bleue d'abord, rouge ensuite.
        blue_team: Team | None = None
        red_team: Team | None = None
        for team in game.teams:
            if team.side == TeamSide.BLUE:
                blue_team = team
            elif team.side == TeamSide.RED:
                red_team = team

        embed = discord.Embed(
            title=title,
            color=COLOR_BLUE,
            timestamp=game.created_at,
        )

        sections: list[str] = []
        teams_to_render = [t for t in (blue_team, red_team) if t is not None]

        for team in teams_to_render:
            body, color = _team_section(team, game.game_duration, phase=1)
            sections.append(body)
            embed.color = color  # dernière couleur dominante (bleu/rouge)

        embed.description = "\n\n".join(sections)
        embed.set_footer(text="Tracker LoL | Phase 1")

        await channel.send(embed=embed)
        logger.info(
            "Embed composition envoyé pour la game %s", game.game_id
        )

    # ═══════════════════════════════════════════════════════════════════
    # Phase 2 — Embed résultat post-game
    # ═══════════════════════════════════════════════════════════════════

    async def send_game_result(self, game: "Game") -> None:
        """Phase 2 : Envoie l'embed de résultat avec les stats complètes.

        Contient le KDA, CS/min, Gold/min, dégâts, vision et les
        objectifs globaux de chaque équipe.
        """
        channel = self._get_channel()
        if channel is None:
            return

        from core.models import TeamSide

        duration_str = _format_duration(game.game_duration)
        title = (
            f"🏆 Résultat — {game.game_mode or 'Partie'} — {duration_str}"
        )

        # Déterminer le vainqueur (plus gros nombre de kills, ou winSide
        # si disponible).  Fallback : on ne colore pas.
        winner_side: TeamSide | None = None
        if len(game.teams) == 2:
            sorted_teams = sorted(game.teams, key=lambda t: t.kills, reverse=True)
            if sorted_teams[0].kills > sorted_teams[1].kills:
                winner_side = sorted_teams[0].side

        # Couleur de l'embed = victoire ou défaite du joueur suivi.
        embed_color = COLOR_DEFEAT
        for team in game.teams:
            if team.side == winner_side:
                for p in team.players:
                    if p.puuid == game.tracked_player_puuid:
                        embed_color = COLOR_VICTORY
                        break

        embed = discord.Embed(
            title=title,
            color=embed_color,
            timestamp=game.updated_at,
        )

        blue_team: Team | None = None
        red_team: Team | None = None
        for team in game.teams:
            if team.side == TeamSide.BLUE:
                blue_team = team
            elif team.side == TeamSide.RED:
                red_team = team

        sections: list[str] = []
        for team in (t for t in (blue_team, red_team) if t is not None):
            body, _ = _team_section(
                team, game.game_duration, phase=2, winner_side=winner_side
            )
            sections.append(body)

        # Objectifs globaux
        objective_lines: list[str] = []
        for team in (t for t in (blue_team, red_team) if t is not None):
            key = _side_key(team.side)
            emoji = "🔵" if key == "blue" else "🔴"
            objective_lines.append(f"{emoji} {_objectives_line(team)}")

        sections.append("\n".join(objective_lines))

        embed.description = "\n\n".join(sections)
        embed.set_footer(text="Tracker LoL | Phase 2")

        await channel.send(embed=embed)
        logger.info(
            "Embed résultat envoyé pour la game %s (match %s)",
            game.game_id,
            game.match_id,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Utilitaire — lancement comme tâche asyncio
    # ═══════════════════════════════════════════════════════════════════

    async def start_as_task(self) -> asyncio.Task[None]:
        """Lance le bot dans sa propre tâche asyncio.

        Renvoie la ``Task`` pour permettre l'annulation côté orchestrateur.
        """
        return asyncio.create_task(self.start())
