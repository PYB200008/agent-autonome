"""Tests de la mémoire court terme (bot/db.py, M1).

La base utilisée est une base SQLite temporaire (fixture tmp_path), jamais la
vraie ``bot.db``. Le temps est simulé via l'horloge injectable (bot/clock.py).
"""

from __future__ import annotations

import datetime as dt

from bot.clock import set_now
from bot.config import Settings
from bot.db import Database

from .helpers import read_message_rows

USER_ID = "424242424242424242"


def test_insert_message_is_stored(db: Database, settings: Settings) -> None:
    """Vérifie M1 : l'insertion d'un message crée bien la ligne en base."""
    conversation_id = db.get_or_create_conversation(USER_ID)
    db.insert_message(conversation_id, "utilisateur", "salut")
    rows = read_message_rows(settings.db_path)
    assert len(rows) == 1
    assert rows[0][0] == "utilisateur"
    assert rows[0][1] == "salut"


def test_recent_messages_limited_to_thirty_db(db: Database, settings: Settings) -> None:
    """Vérifie M1 : la relecture ne renvoie que les 30 derniers messages, en ordre chronologique."""
    conversation_id = db.get_or_create_conversation(USER_ID)
    for i in range(1, 41):
        auteur = "utilisateur" if i % 2 == 1 else "bot"
        db.insert_message(conversation_id, auteur, f"message-{i:02d}")
    recent = db.recent_messages(conversation_id, settings.memory_max_messages)
    assert len(recent) == 30
    assert recent[0].contenu == "message-11"
    assert recent[-1].contenu == "message-40"
    assert recent[0].auteur == "utilisateur"
    assert recent[-1].auteur == "bot"
    assert [m.auteur for m in recent] == [
        "utilisateur" if i % 2 == 1 else "bot" for i in range(11, 41)
    ]


def test_same_user_gets_stable_conversation(db: Database) -> None:
    """Vérifie M1 : un même utilisateur retombe sur la même conversation, un autre non."""
    first = db.get_or_create_conversation(USER_ID)
    second = db.get_or_create_conversation(USER_ID)
    assert first == second
    other = db.get_or_create_conversation("999999999999999999")
    assert other != first


def test_message_timestamp_follows_simulated_clock(db: Database, settings: Settings) -> None:
    """Vérifie le temps simulé : l'horodatage en base suit l'horloge injectée."""
    fixed = dt.datetime(2026, 3, 14, 9, 5, tzinfo=dt.timezone.utc)
    set_now(lambda: fixed)
    conversation_id = db.get_or_create_conversation(USER_ID)
    db.insert_message(conversation_id, "utilisateur", "salut")
    rows = read_message_rows(settings.db_path)
    assert rows[0][2] == fixed.isoformat()


def test_memory_survives_database_restart(settings: Settings) -> None:
    """Vérifie la persistance M1 : les messages survivent à une réouverture de la base."""
    db = Database(settings.db_path)
    conversation_id = db.get_or_create_conversation(USER_ID)
    db.insert_message(conversation_id, "utilisateur", "salut")
    db.insert_message(conversation_id, "bot", "coucou")
    db.close()

    reopened = Database(settings.db_path)
    try:
        recent = reopened.recent_messages(conversation_id, 30)
    finally:
        reopened.close()
    assert [(m.auteur, m.contenu) for m in recent] == [
        ("utilisateur", "salut"),
        ("bot", "coucou"),
    ]