"""Accès SQLite : schéma et opérations de base pour la mémoire du bot.

Tables créées de manière idempotente :
- ``conversations`` : une ligne par conversation (état et horodatages pour les
  lots 3 à 5) ;
- ``messages`` : les messages échangés, base de la mémoire court terme (M1) ;
- ``resumes`` : résumés de fin de conversation (lot 3, M2) ;
- ``faits`` : faits durables extraits des conversations (lot 5, M3) ;
- ``relances`` : relances planifiées persistées (lot 4, R-relances).

Aucune logique métier supplémentaire n'est ajoutée pour les lots futurs.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from bot.clock import now

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utilisateur_id TEXT NOT NULL,
        etat TEXT NOT NULL DEFAULT 'active',
        dernier_message_at TEXT,
        creee_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id),
        auteur TEXT NOT NULL,
        contenu TEXT NOT NULL,
        horodatage TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
    ON messages (conversation_id, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id),
        contenu TEXT NOT NULL,
        creee_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS faits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contenu TEXT NOT NULL UNIQUE,
        creee_at TEXT NOT NULL,
        mise_a_jour_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS relances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id),
        planifiee_pour TEXT NOT NULL,
        etat TEXT NOT NULL DEFAULT 'planifiee',
        tentative INTEGER NOT NULL DEFAULT 0,
        creee_at TEXT NOT NULL
    )
    """,
)


@dataclass(frozen=True)
class MemoryMessage:
    """Message mémorisé, prêt à être injecté dans le contexte envoyé au LLM."""

    auteur: str
    contenu: str
    horodatage: str


class Database:
    """Connexion SQLite unique, protégée par un verrou.

    Le client Discord et la boucle de fond tournent dans le même thread asyncio,
    mais le verrou permet aussi un accès sans risque depuis un thread de test.
    """

    def __init__(self, path: str | Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            for statement in SCHEMA_STATEMENTS:
                self._conn.execute(statement)
            self._conn.commit()

    def close(self) -> None:
        """Ferme la connexion SQLite."""
        with self._lock:
            self._conn.close()

    def get_or_create_conversation(self, utilisateur_id: str) -> int:
        """Renvoie l'identifiant stable de la conversation de l'utilisateur (M1).

        Lot 1 : une seule conversation par utilisateur ; elle est créée au
        premier message et son identifiant est conservé en base pour les lots
        suivants.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM conversations WHERE utilisateur_id = ? ORDER BY id LIMIT 1",
                (utilisateur_id,),
            ).fetchone()
            if row is not None:
                row_id = row["id"]
                assert row_id is not None
                return int(row_id)
            cursor = self._conn.execute(
                "INSERT INTO conversations (utilisateur_id, etat, creee_at) VALUES (?, 'active', ?)",
                (utilisateur_id, now().isoformat()),
            )
            self._conn.commit()
            lastrowid = cursor.lastrowid
            assert lastrowid is not None
            return int(lastrowid)

    def insert_message(self, conversation_id: int, auteur: str, contenu: str) -> int:
        """Insère un message dans la conversation et renvoie son identifiant."""
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO messages (conversation_id, auteur, contenu, horodatage) VALUES (?, ?, ?, ?)",
                (conversation_id, auteur, contenu, now().isoformat()),
            )
            self._conn.commit()
            lastrowid = cursor.lastrowid
            assert lastrowid is not None
            return int(lastrowid)

    def recent_messages(self, conversation_id: int, limit: int) -> list[MemoryMessage]:
        """Renvoie les ``limit`` derniers messages, du plus ancien au plus récent (M1).

        L'ordre de la table (``id``) sert de référence chronologique.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT auteur, contenu, horodatage FROM messages "
                "WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        return [
            MemoryMessage(auteur=row["auteur"], contenu=row["contenu"], horodatage=row["horodatage"])
            for row in reversed(rows)
        ]