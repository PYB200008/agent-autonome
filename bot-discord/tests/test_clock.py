"""Tests de l'horloge injectable (bot/clock.py, temps simulé).

Aucun test de ce module n'attend en temps réel : l'horloge est pilotée par
``set_now`` et ``reset_now``.
"""

from __future__ import annotations

import datetime as dt

from bot.clock import now, reset_now, set_now


def test_set_now_imposes_simulated_time() -> None:
    """Vérifie que set_now impose le temps simulé renvoyé par now()."""
    fixed = dt.datetime(2026, 3, 14, 9, 5, tzinfo=dt.timezone.utc)
    set_now(lambda: fixed)
    assert now() == fixed


def test_reset_now_restores_real_clock() -> None:
    """Vérifie que reset_now rétablit l'horloge réelle après un test."""
    fixed = dt.datetime(2026, 3, 14, 9, 5, tzinfo=dt.timezone.utc)
    set_now(lambda: fixed)
    reset_now()
    real = dt.datetime.now().astimezone()
    assert abs((now() - real).total_seconds()) < 5.0