"""Helpers de vérification partagés par les tests (lecture directe de la base)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


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