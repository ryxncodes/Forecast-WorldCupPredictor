"use client";

import { useEffect, useMemo, useState } from "react";
import { formatDateTimeET, formatDayKeyET, formatDayLabelET, formatLongDateTimeET, parseApiDate } from "@/lib/format";
import type { Match, MatchTimelineEvent } from "@/lib/types";
import { CheckIcon, ChevronIcon, ClockIcon } from "./Icons";

type Props = { matches: Match[] };

function formatPercent(value: number) {
  const percent = value * 100;
  if (percent === 0) return "0%";
  if (percent < 10) return `${percent.toFixed(1)}%`;
  return `${Math.round(percent)}%`;
}

function sortMatchesForFilter(matches: Match[], filter: "all" | "live" | "upcoming" | "completed") {
  return [...matches].sort((a, b) => {
    const kickoffA = parseApiDate(a.kickoff).getTime();
    const kickoffB = parseApiDate(b.kickoff).getTime();
    if (filter === "completed") return kickoffB - kickoffA || b.match_number - a.match_number;
    return kickoffA - kickoffB || a.match_number - b.match_number;
  });
}

function eventLabel(event: MatchTimelineEvent) {
  const tags = [
    event.penalty ? "pen." : "",
    event.own_goal ? "own goal" : "",
  ].filter(Boolean);
  return tags.length ? `${event.type} (${tags.join(", ")})` : event.type;
}

function hasShootoutScore(match: Match) {
  return match.details?.home_shootout_score != null || match.details?.away_shootout_score != null;
}

function formatScore(match: Match) {
  if (match.status === "pre") return "–";
  const homeScore = match.home_score ?? 0;
  const awayScore = match.away_score ?? 0;
  if (hasShootoutScore(match)) {
    return `${homeScore} (${match.details.home_shootout_score ?? 0}) – ${awayScore} (${match.details.away_shootout_score ?? 0})`;
  }
  return `${homeScore} – ${awayScore}`;
}

export function MatchList({ matches }: Props) {
  const hasLiveMatches = matches.some((match) => match.status === "in");
  const hasUpcomingMatches = matches.some((match) => match.status === "pre");
  const defaultFilter = hasLiveMatches ? "live" : hasUpcomingMatches ? "upcoming" : "all";
  const [filter, setFilter] = useState<"all" | "live" | "upcoming" | "completed">(() => defaultFilter);
  const [autoFilter, setAutoFilter] = useState(true);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(() => new Set(matches.filter((match) => match.status === "in").map((match) => match.id)));

  useEffect(() => {
    if (!autoFilter) return;
    setFilter(defaultFilter);
  }, [autoFilter, defaultFilter]);

  useEffect(() => {
    const liveIds = matches.filter((match) => match.status === "in").map((match) => match.id);
    if (!liveIds.length) return;
    setExpandedIds((current) => new Set([...current, ...liveIds]));
  }, [matches]);

  const visibleMatches = useMemo(() => {
    const filtered = matches.filter((match) => (
      filter === "all"
      || (filter === "completed" && match.status === "post")
      || (filter === "live" && match.status === "in")
      || (filter === "upcoming" && match.status === "pre")
    ));
    return sortMatchesForFilter(filtered, filter);
  }, [filter, matches]);

  const groupedMatches = useMemo(() => {
    const groups: { key: string; label: string; matches: Match[] }[] = [];
    const groupByKey = new Map<string, { key: string; label: string; matches: Match[] }>();
    for (const match of visibleMatches) {
      const key = formatDayKeyET(match.kickoff);
      const label = formatDayLabelET(match.kickoff);
      const existing = groupByKey.get(key);
      if (existing) existing.matches.push(match);
      else {
        const group = { key, label, matches: [match] };
        groupByKey.set(key, group);
        groups.push(group);
      }
    }
    return groups;
  }, [visibleMatches]);

  function toggleExpanded(matchId: number) {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(matchId)) next.delete(matchId);
      else next.add(matchId);
      return next;
    });
  }

  return (
    <section id="matches" className="matches-section" aria-labelledby="matches-heading">
      <div className="matches-title"><h2 id="matches-heading">Tournament matches</h2><div className="match-filters" aria-label="Filter matches">{(["all", "live", "upcoming", "completed"] as const).map((value) => <button aria-pressed={filter === value} className={filter === value ? "active" : ""} type="button" key={value} onClick={() => { setAutoFilter(false); setFilter(value); }}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div></div>
      <div className="match-list">
        {!groupedMatches.length ? <p className="match-empty-state">No {filter === "all" ? "" : filter} matches to show right now.</p> : null}
        {groupedMatches.map((group) => <div className="match-day-group" key={group.key}>
          <div className="match-day-heading"><span>{group.label}</span><small>{group.matches.length} match{group.matches.length === 1 ? "" : "es"}</small></div>
          {group.matches.map((match) => {
          const expanded = expandedIds.has(match.id);
          const live = match.status === "in";
          const pendingScore = match.status === "pre";
          const canShowPrediction = match.status !== "post";
          const projectedMatchup = match.matchup_status === "projected";
          const knockoutPrediction = match.prediction.market === "advance" || match.stage !== "group";
          const details = match.details ?? {};
          const goals = details.goals ?? [];
          const timeline = details.events ?? [];
          const broadcasts = details.broadcasts ?? [];
          const shootoutLabel = hasShootoutScore(match) ? `${match.home_team} ${details.home_shootout_score ?? 0}, ${match.away_team} ${details.away_shootout_score ?? 0}` : null;
          const decisionLabel = details.decided_by === "penalties"
            ? `Advanced on penalties${details.winner ? `: ${details.winner}` : ""}`
            : details.decided_by === "extra_time" && details.winner
              ? `Advanced after extra time: ${details.winner}`
              : null;
          const predictionRows = knockoutPrediction
            ? [
              { label: match.home_team, value: match.prediction.home_win_probability },
              { label: match.away_team, value: match.prediction.away_win_probability },
            ]
            : [
              { label: match.home_team, value: match.prediction.home_win_probability },
              { label: "Draw", value: match.prediction.draw_probability },
              { label: match.away_team, value: match.prediction.away_win_probability },
            ];
          const modelLeader = [...predictionRows].sort((a, b) => b.value - a.value)[0];
          return <div className={expanded ? "match-row-wrap expanded" : "match-row-wrap"} key={match.id}>
            <button className={pendingScore ? "match-row pending-score" : "match-row"} type="button" onClick={() => toggleExpanded(match.id)} aria-expanded={expanded}>
              <span className="match-time"><small>#{match.match_number}</small>{formatDateTimeET(match.kickoff)}</span><span className="match-group">{match.group}</span><span className="match-teams"><span className="team-name"><strong>{match.home_team}</strong>{projectedMatchup ? <em>Projected</em> : null}</span><small>vs</small><span className="team-name"><strong>{match.away_team}</strong>{projectedMatchup ? <em>Projected</em> : null}</span></span><span className={live ? "score live" : "score"}>{formatScore(match)}</span><span className="match-edge">{canShowPrediction ? `${modelLeader.label} ${formatPercent(modelLeader.value)}${knockoutPrediction ? " to advance" : ""}` : details.winner ? `${details.winner} advanced` : "Final"}</span><span className={match.completed ? "status completed" : live ? "status live" : "status"}>{match.completed ? <CheckIcon /> : <ClockIcon />}<span><strong>{live ? "Live" : match.completed ? "Completed" : "Scheduled"}</strong><small>{live ? match.status_detail : match.venue}</small></span><ChevronIcon className={expanded ? "chevron open" : "chevron"} /></span>
            </button>
            {expanded ? <div className="match-details-panel">
              <div className="match-detail-grid">
                <div><span>Kickoff</span><strong>{formatLongDateTimeET(match.kickoff)}</strong></div>
                <div><span>Venue</span><strong>{details.venue_full_name || match.venue}</strong><small>{[details.venue_city, details.venue_country].filter(Boolean).join(", ")}</small></div>
                <div><span>Attendance</span><strong>{details.attendance ? details.attendance.toLocaleString() : "TBD"}</strong></div>
                <div><span>Broadcast</span><strong>{broadcasts.length ? broadcasts.join(", ") : "TBD"}</strong></div>
                {shootoutLabel ? <div><span>Shootout</span><strong>{shootoutLabel}</strong><small>{decisionLabel}</small></div> : null}
                {!shootoutLabel && decisionLabel ? <div><span>Decision</span><strong>{decisionLabel}</strong></div> : null}
              </div>
              {canShowPrediction ? <div className="match-prediction-card">
                <div><strong>{knockoutPrediction ? "Model advance chance" : "Model prediction"}</strong><span>Expected goals: {match.home_team} {match.prediction.home_expected_goals.toFixed(2)}, {match.away_team} {match.prediction.away_expected_goals.toFixed(2)}</span></div>
                <div className="match-prediction-bars">{predictionRows.map((row) => <div key={row.label}><span>{row.label}</span><strong>{formatPercent(row.value)}</strong><em><i style={{ width: `${row.value * 100}%` }} /></em></div>)}</div>
              </div> : null}
              {goals.length ? <div className="match-events-block">
                <strong>Goals</strong>
                <ul>{goals.map((event, index) => <li key={`${event.minute}-${event.player}-${index}`}><span>{event.minute}</span><div><strong>{event.player || event.team}</strong><small>{event.team} · {eventLabel(event)}</small></div></li>)}</ul>
              </div> : null}
              {timeline.length && !goals.length ? <div className="match-events-block">
                <strong>Match events</strong>
                <ul>{timeline.map((event, index) => <li key={`${event.minute}-${event.type}-${index}`}><span>{event.minute}</span><div><strong>{event.player || event.team}</strong><small>{event.team} · {eventLabel(event)}</small></div></li>)}</ul>
              </div> : null}
              {!canShowPrediction && !goals.length && !timeline.length ? <p className="match-empty-detail">No scorer timeline is available from the public feed for this match yet.</p> : null}
            </div> : null}
          </div>;
        })}
        </div>)}
      </div>
      <p className="matches-note">Scores refresh automatically. Live scores are displayed immediately; standings, ratings, and tournament forecasts update only after the result is final.</p>
    </section>
  );
}
