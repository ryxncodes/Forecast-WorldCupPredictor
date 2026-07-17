from collections import defaultdict
from datetime import UTC, datetime
import hashlib
import math

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import KnockoutPredictionSnapshot
from .bracket_service import index_projection_matches
from .accuracy_service import _most_likely_score, _selected_outcome
from .knockout_schedule import KNOCKOUT_SCHEDULE, ROUND_LABELS
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
            "predicted_score_probability": snapshot.predicted_score_probability,
        })
    return {
        "matches_with_predictions": len(matches),
        "total_revisions": sum(len(rows) for rows in revisions_by_match.values()),
        "matches": matches,
    }


def knockout_accuracy(
    db: Session,
    knockout_events: dict[int, dict],
    now: datetime | None = None,
) -> dict:
    """Score immutable knockout picks against the two-team advance market."""
    inventory = knockout_prediction_inventory(db, now=now)
    matches = []
    for prediction in inventory["matches"]:
        match_number = prediction["match_number"]
        schedule = KNOCKOUT_SCHEDULE.get(match_number)
        if schedule is None:
            continue
        round_name = schedule[0]
        event = knockout_events.get(match_number, {})
        event_present = match_number in knockout_events
        event_complete = event.get("state") == "post" or event.get("completed") is True
        event_matches_prediction = (
            event.get("home") == prediction["home_team"]
            and event.get("away") == prediction["away_team"]
        )
        home_score = event.get("home_score") if event_matches_prediction else None
        away_score = event.get("away_score") if event_matches_prediction else None
        actual_advancer = (
            event.get("winner") if event_complete and event_matches_prediction else None
        )
        if (
            event_complete
            and actual_advancer is None
            and home_score is not None
            and away_score is not None
        ):
            if home_score > away_score:
                actual_advancer = prediction["home_team"]
            elif away_score > home_score:
                actual_advancer = prediction["away_team"]

        decisive_probability = prediction["home_win_probability"] + prediction["away_win_probability"]
        home_advance = prediction["home_win_probability"] / decisive_probability
        away_advance = prediction["away_win_probability"] / decisive_probability
        predicted_advancer = (
            prediction["home_team"] if home_advance >= away_advance else prediction["away_team"]
        )
        scored = actual_advancer in (prediction["home_team"], prediction["away_team"])
        if event_complete and not event_matches_prediction:
            row_status = "completed_unscored"
            unscored_reason = "participant_mismatch"
        elif event_complete and scored:
            row_status = "scored"
            unscored_reason = None
        elif event_complete:
            row_status = "completed_unscored"
            unscored_reason = "winner_unavailable"
        elif event_matches_prediction and event.get("state") == "in":
            row_status = "in_progress"
            unscored_reason = None
        elif event_present and not event_matches_prediction:
            row_status = "unavailable"
            unscored_reason = "participant_mismatch"
        elif prediction["prediction_status"] == "updating":
            row_status = "upcoming"
            unscored_reason = None
        else:
            row_status = "unavailable"
            unscored_reason = "result_unavailable"
        actual_probability = (
            home_advance if actual_advancer == prediction["home_team"] else away_advance
        ) if scored else None
        matches.append({
            **prediction,
            "round": round_name,
            "round_label": ROUND_LABELS[round_name],
            "prediction_source": "locked" if prediction["source"] == "live" else "reconstructed",
            "home_advance_probability": home_advance,
            "away_advance_probability": away_advance,
            "predicted_advancer": predicted_advancer,
            "home_score": home_score,
            "away_score": away_score,
            "actual_advancer": actual_advancer,
            "row_status": row_status,
            "unscored_reason": unscored_reason,
            "completed": event_complete,
            "picked_correct": predicted_advancer == actual_advancer if scored else None,
            "exact_score": (
                prediction["predicted_home_score"] == home_score
                and prediction["predicted_away_score"] == away_score
            ) if event_complete and home_score is not None and away_score is not None else None,
            "brier_score": (
                (home_advance - (1 if actual_advancer == prediction["home_team"] else 0)) ** 2
                + (away_advance - (1 if actual_advancer == prediction["away_team"] else 0)) ** 2
            ) if scored else None,
            "log_loss": -math.log(max(actual_probability, 1e-12)) if actual_probability is not None else None,
        })

    scored_rows = [match for match in matches if match["row_status"] == "scored"]
    picked_correct = sum(bool(match["picked_correct"]) for match in scored_rows)
    completed_events = sum(
        event.get("state") == "post" or event.get("completed") is True
        for event in knockout_events.values()
    )
    return {
        "matches_with_predictions": inventory["matches_with_predictions"],
        "total_revisions": inventory["total_revisions"],
        "completed_matches": completed_events,
        "scored_matches": len(scored_rows),
        "upcoming_matches": sum(match["row_status"] == "upcoming" for match in matches),
        "in_progress_matches": sum(match["row_status"] == "in_progress" for match in matches),
        "unavailable_matches": sum(
            match["row_status"] in ("completed_unscored", "unavailable") for match in matches
        ),
        "unscored_completed_matches": max(completed_events - len(scored_rows), 0),
        "locked_predictions": sum(match["prediction_source"] == "locked" for match in scored_rows),
        "reconstructed_predictions": sum(
            match["prediction_source"] == "reconstructed" for match in scored_rows
        ),
        "picked_correct": picked_correct,
        "pick_accuracy": picked_correct / len(scored_rows) if scored_rows else 0,
        "average_brier_score": (
            sum(match["brier_score"] for match in scored_rows) / len(scored_rows)
            if scored_rows else 0
        ),
        "average_log_loss": (
            sum(match["log_loss"] for match in scored_rows) / len(scored_rows)
            if scored_rows else 0
        ),
        "matches": sorted(matches, key=lambda match: match["match_number"], reverse=True),
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
    """Stage a changed pre-kickoff pick; return the frozen pick afterward."""
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
    db.flush()
    return snapshot


def reconstruct_completed_knockout_predictions(
    db: Session,
    *,
    knockout_events: dict[int, dict],
    post_group_ratings: dict[str, float],
    reconstructed_at: datetime,
) -> list[KnockoutPredictionSnapshot]:
    """Stage missing replayed picks chronologically; the caller commits."""
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
        db.flush()
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
