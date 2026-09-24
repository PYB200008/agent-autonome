"""Horloge centralisée pour les horodatages du bot.

Tout le code utilise ``now()`` de ce module plutôt que ``datetime.now()``
directement, afin que les tests puissent simuler le temps via ``set_now``.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

# Type d'une fonction d'horloge : renvoie un datetime local avec fuseau horaire.
NowFunc = Callable[[], dt.datetime]

_clock: NowFunc = lambda: dt.datetime.now().astimezone()


def set_now(func: NowFunc) -> None:
    """Remplace l'horloge par ``func`` (temps simulé pour les tests)."""
    global _clock
    _clock = func


def reset_now() -> None:
    """Rétablit l'horloge réelle après un test."""
    set_now(lambda: dt.datetime.now().astimezone())


def now() -> dt.datetime:
    """Renvoie l'horodatage courant, en heure locale avec fuseau horaire."""
    return _clock()