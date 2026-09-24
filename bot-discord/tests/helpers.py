"""Helpers de vérification partagés par les tests (base et temps simulé).

La lecture directe de la base sert aux assertions de mémoire (M1). Le faux
sommeil et l'attente de fin de traitement servent aux tests du lot 2 (S1-S3,
S8) : le traitement des rafales est lancé dans des tâches asyncio par le
client, et aucun test ne doit attendre en temps réel.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any


def read_message_rows(db_path: Path) -> list[tuple[str, str, str]]:
    """Lit la table messages via une connexion séparée, dans l'ordre d'insertion.

    Renvoie des triplets (auteur, contenu, horodatage). Les opérations du code
    testé sont commitées immédiatement, la lecture concurrente est donc sûre.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT auteur, contenu, horodatage FROM messages ORDER BY id"
        ).fetchall()
    return [(row["auteur"], row["contenu"], row["horodatage"]) for row in rows]


async def instant_sleep(_: float) -> None:
    """Faux sommeil : ne bloque jamais la boucle d'événements (temps simulé)."""


async def wait_for_burst_processing(client: Any) -> None:
    """Attend la fin du traitement asynchrone de la dernière rafale (S8).

    ``on_message`` lance l'attente de fin de rafale puis le traitement dans des
    tâches asyncio distinctes ; ce helper cède la main à la boucle jusqu'à la
    création puis la complétion de la tâche de traitement. Avec le faux sommeil
    instantané injecté, aucune de ces étapes n'attend en temps réel.

    À n'utiliser qu'après avoir transmis au client un message de l'utilisateur
    autorisé (une rafale doit être en attente).
    """
    while client._burst_task is not None and not client._burst_task.done():
        await asyncio.sleep(0)
    task = client._processing_task
    while task is None or task.done():
        await asyncio.sleep(0)
        task = client._processing_task
    await task