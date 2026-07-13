from collections import defaultdict
from datetime import UTC, datetime
import hashlib

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import KnockoutPredictionSnapshot
from .bracket_service import index_projection_matches
from .accuracy_service import _most_likely_score, _selected_outcome
from .knockout_schedule import KNOCKOUT_SCHEDULE
from .match_model import expected_goals, outcome_probabilities
from .model_parameters import MODEL_VERSION
from .ratings import update_rating_pair


def _naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def knockout_prediction_inventory(db: Session, now: datetime | None = None) -> dict:
    """Return the latest eligible revision and provenance for each knockout match."""
    now = _naive_utc(now or datetime.now(UTC))
    revisions_by_match = defaultdict(list)
    for snapshot in db.scalars(
        select(KnockoutPredictionSnapshot).order_by(
            KnockoutPredictionSnapshot.match_number,
            KnockoutPredictionSnapshot.generated_at,
            KnockoutPredictionSnapshot.id,
        )
    ):
        revisions_by_match[snapshot.match_number].append(snapshot)

    matches = []
    for match_number, revisions in sorted(revisions_by_match.items()):
        eligible = [
            snapshot for snapshot in revisions
            if snapshot.source == "reconstructed"
            or _naive_utc(snapshot.generated_at) <= _naive_utc(snapshot.kickoff)
        ]
        if not eligible:
            continue
        snapshot = eligible[-1]
        kickoff = _naive_utc(snapshot.kickoff)
        matches.append({
            "snapshot_id": snapshot.id,
            "match_number": match_number,
            "kickoff": snapshot.kickoff.isoformat(),
            "generated_at": snapshot.generated_at.isoformat(),
            "prediction_status": "frozen" if now >= kickoff else "updating",
            "source": snapshot.source,
            "model_version": snapshot.model_version,
            "input_fingerprint": snapshot.input_fingerprint,
            "revision_count": len(eligible),
            "home_team": snapshot.home_team,
            "away_team": snapshot.away_team,
            "home_team_rating": snapshot.home_team_rating,
            "away_team_rating": snapshot.away_team_rating,
            "home_expected_goals": snapshot.home_expected_goals,
            "away_expected_goals": snapshot.away_expected_goals,
            "home_win_probability": snapshot.home_win_probability,
            "draw_probability": snapshot.draw_probability,
            "away_win_probability": snapshot.away_win_probability,
            "predicted_outcome": snapshot.predicted_outcome,
            "predicted_home_score": snapshot.predicted_home_score,
            "predicted_away_score": snapshot.predicted_away_score,
        })
    return {
        "matches_with_predictions": len(matches),
        "total_revisions": sum(len(rows) for rows in revisions_by_match.values()),
        "matches": matches,
    }


def latest_eligible_prediction(
    db: Session,
    match_number: int,
    kickoff: datetime,
) -> KnockoutPredictionSnapshot | None:
    return db.scalar(
        select(KnockoutPredictionSnapshot)
        .where(
            KnockoutPredictionSnapshot.match_number == match_number,
            or_(
                KnockoutPredictionSnapshot.generated_at <= kickoff,
                KnockoutPredictionSnapshot.source == "reconstructed",
            ),
        )
        .order_by(KnockoutPredictionSnapshot.generated_at.desc(), KnockoutPredictionSnapshot.id.desc())
        .limit(1)
    )


def record_knockout_prediction(
    db: Session,
    *,
    match_number: int,
    kickoff: datetime,
    home_team: str,
    away_team: str,
    home_rating: float,
    away_rating: float,
    input_fingerprint: str,
    generated_at: datetime,
    source: str = "live",
) -> KnockoutPredictionSnapshot | None:
    """Append a changed pre-kickoff prediction; return the frozen pick afterward."""
    frozen = latest_eligible_prediction(db, match_number, kickoff)
    if generated_at >= kickoff:
        return frozen

    existing = db.scalar(
        select(KnockoutPredictionSnapshot).where(
            KnockoutPredictionSnapshot.match_number == match_number,
            KnockoutPredictionSnapshot.input_fingerprint == input_fingerprint,
        )
    )
    if existing is not None:
        return existing

    home_xg, away_xg = expected_goals(home_rating, away_rating)
    home_win, draw, away_win = outcome_probabilities(home_xg, away_xg)
    probabilities = {"home": home_win, "draw": draw, "away": away_win}
    score_pick = _most_likely_score(home_xg, away_xg)
    snapshot = KnockoutPredictionSnapshot(
        match_number=match_number,
        kickoff=kickoff,
        generated_at=generated_at,
        source=source,
        input_fingerprint=input_fingerprint,
        model_version=MODEL_VERSION,
        home_team=home_team,
        away_team=away_team,
        home_team_rating=home_rating,
        away_team_rating=away_rating,
        home_expected_goals=home_xg,
        away_expected_goals=away_xg,
        home_win_probability=home_win,
        draw_probability=draw,
        away_win_probability=away_win,
        predicted_outcome=_selected_outcome(probabilities),
        predicted_home_score=score_pick.home_goals,
        predicted_away_score=score_pick.away_goals,
        predicted_score_probability=score_pick.probability,
    )
    db.add(snapshot)
    db.commit()
    return snapshot


def reconstruct_completed_knockout_predictions(
    db: Session,
    *,
    knockout_events: dict[int, dict],
    post_group_ratings: dict[str, float],
    reconstructed_at: datetime,
) -> list[KnockoutPredictionSnapshot]:
    """Replay completed knockouts chronologically and fill each missing pick once."""
    ratings = dict(post_group_ratings)
    prior_results = []
    inserted = []
    ordered_events = sorted(
        (
            (match_number, event)
            for match_number, event in knockout_events.items()
            if match_number in KNOCKOUT_SCHEDULE and event.get("state") == "post"
        ),
        key=lambda item: (KNOCKOUT_SCHEDULE[item[0]][1], item[0]),
    )
    for match_number, event in ordered_events:
        home = event.get("home")
        away = event.get("away")
        home_score = event.get("home_score")
        away_score = event.get("away_score")
        if (
            not home or not away
            or home not in ratings or away not in ratings
            or home_score is None or away_score is None
        ):
            continue

        existing = db.scalar(
            select(KnockoutPredictionSnapshot)
            .where(KnockoutPredictionSnapshot.match_number == match_number)
            .limit(1)
        )
        if existing is None:
            home_xg, away_xg = expected_goals(ratings[home], ratings[away])
            home_win, draw, away_win = outcome_probabilities(home_xg, away_xg)
            probabilities = {"home": home_win, "draw": draw, "away": away_win}
            score_pick = _most_likely_score(home_xg, away_xg)
            cutoff = KNOCKOUT_SCHEDULE[match_number][1]
            fingerprint = hashlib.sha256(
                f"reconstructed:{cutoff}:{'|'.join(prior_results)}".encode()
            ).hexdigest()
            snapshot = KnockoutPredictionSnapshot(
                match_number=match_number,
                kickoff=datetime.fromisoformat(cutoff.replace("Z", "+00:00")),
                generated_at=reconstructed_at,
                source="reconstructed",
                input_fingerprint=fingerprint,
                model_version=MODEL_VERSION,
                home_team=home,
                away_team=away,
                home_team_rating=ratings[home],
                away_team_rating=ratings[away],
                home_expected_goals=home_xg,
                away_expected_goals=away_xg,
                home_win_probability=home_win,
                draw_probability=draw,
                away_win_probability=away_win,
                predicted_outcome=_selected_outcome(probabilities),
                predicted_home_score=score_pick.home_goals,
                predicted_away_score=score_pick.away_goals,
                predicted_score_probability=score_pick.probability,
            )
            db.add(snapshot)
            inserted.append(snapshot)

        pair = update_rating_pair(ratings[home], ratings[away], home_score, away_score)
        ratings[home], ratings[away] = pair.home, pair.away
        prior_results.append(f"{match_number}:{home}:{home_score}:{away_score}:{away}")

    if inserted:
        db.commit()
    return inserted


def record_canonical_knockout_predictions(
    db: Session,
    *,
    bracket_projection: dict,
    knockout_events: dict[int, dict],
    live_ratings: dict[str, float] | list[dict],
    current_time: datetime,
    result_fingerprint: str,
) -> list[KnockoutPredictionSnapshot]:
    """Append current live picks for confirmed future knockout matchups only."""
    ratings_by_name = (
        live_ratings
        if isinstance(live_ratings, dict)
        else {team["name"]: team["rating"] for team in live_ratings}
    )
    matches = index_projection_matches(bracket_projection)

    inserted = []
    for match_number, event in sorted(knockout_events.items()):
        match = matches.get(match_number)
        schedule = KNOCKOUT_SCHEDULE.get(match_number)
        home = event.get("home")
        away = event.get("away")
        if not match or not schedule or not home or not away:
            continue
        if match.get("home", {}).get("team") != home or match.get("away", {}).get("team") != away:
            continue
        if home not in ratings_by_name or away not in ratings_by_name:
            continue

        kickoff = datetime.fromisoformat(schedule[1].replace("Z", "+00:00"))
        if current_time >= kickoff:
            continue
        fingerprint = (
            f"{result_fingerprint}:{match_number}:{home}:{away}:"
            f"{ratings_by_name[home]:.6f}:{ratings_by_name[away]:.6f}"
        )
        existing = db.scalar(
            select(KnockoutPredictionSnapshot).where(
                KnockoutPredictionSnapshot.match_number == match_number,
                KnockoutPredictionSnapshot.input_fingerprint == fingerprint,
            )
        )
        if existing is not None:
            continue
        snapshot = record_knockout_prediction(
            db,
            match_number=match_number,
            kickoff=kickoff,
            home_team=home,
            away_team=away,
            home_rating=ratings_by_name[home],
            away_rating=ratings_by_name[away],
            input_fingerprint=fingerprint,
            generated_at=current_time,
        )
        if snapshot is not None:
            inserted.append(snapshot)
    return inserted
