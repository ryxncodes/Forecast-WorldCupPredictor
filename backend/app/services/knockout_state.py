from dataclasses import dataclass
from time import monotonic
from typing import Callable

from .live_sync import knockout_match_overrides


KNOCKOUT_STATE_TTL_SECONDS = 60


@dataclass(frozen=True)
class KnockoutState:
    scoreboard: dict | None
    events: dict[int, dict]


_STATE_CACHE: tuple[float, object, KnockoutState] | None = None


def knockout_state(
    scoreboard_loader: Callable[[], dict],
    event_parser: Callable[[dict], dict[int, dict]] = knockout_match_overrides,
) -> KnockoutState:
    """Return one parsed ESPN knockout revision shared by all public endpoints."""
    global _STATE_CACHE
    now = monotonic()
    if _STATE_CACHE is not None:
        created_at, loader, state = _STATE_CACHE
        cached_loader, cached_parser = loader
        if cached_loader is scoreboard_loader and cached_parser is event_parser and now - created_at < KNOCKOUT_STATE_TTL_SECONDS:
            return state

    try:
        scoreboard = scoreboard_loader()
        state = KnockoutState(scoreboard, event_parser(scoreboard))
    except Exception:
        state = KnockoutState(None, {})
    _STATE_CACHE = (now, (scoreboard_loader, event_parser), state)
    return state
