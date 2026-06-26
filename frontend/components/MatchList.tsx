"use client";

import { useEffect, useMemo, useState } from "react";
import type { Match, MatchTimelineEvent } from "@/lib/types";
import { CheckIcon, ChevronIcon, ClockIcon } from "./Icons";

type Props = { matches: Match[] };

function formatKickoff(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatLongKickoff(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatPercent(value: number) {
  const percent = value * 100;
  if (percent === 0) return "0%";
  if (percent < 10) return `${percent.toFixed(1)}%`;
  return `${Math.round(percent)}%`;
}

function eventLabel(event: MatchTimelineEvent) {
  const tags = [
    event.penalty ? "pen." : "",
    event.own_goal ? "own goal" : "",
  ].filter(Boolean);
  return tags.length ? `${event.type} (${tags.join(", ")})` : event.type;
}

export function MatchList({ matches }: Props) {
  const hasLiveMatches = matches.some((match) => match.status === "in");
  const [filter, setFilter] = useState<"all" | "live" | "upcoming" | "completed">(() => hasLiveMatches ? "live" : "all");
  const [autoFilter, setAutoFilter] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    if (!autoFilter) return;
    setFilter(hasLiveMatches ? "live" : "all");
  }, [autoFilter, hasLiveMatches]);

  const visibleMatches = useMemo(() => {
    const filtered = matches.filter((match) => (
      filter === "all"
      || (filter === "completed" && match.status === "post")
      || (filter === "live" && match.status === "in")
      || (filter === "upcoming" && match.status === "pre")
    ));
    if (filter !== "completed") return filtered;
    return [...filtered].sort((a, b) => new Date(b.kickoff).getTime() - new Date(a.kickoff).getTime());
  }, [filter, matches]);

  return (
    <section id="matches" className="matches-section" aria-labelledby="matches-heading">
      <div className="matches-title"><h2 id="matches-heading">Group-stage matches</h2><div className="match-filters" aria-label="Filter matches">{(["all", "live", "upcoming", "completed"] as const).map((value) => <button className={filter === value ? "active" : ""} type="button" key={value} onClick={() => { setAutoFilter(false); setFilter(value); }}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div></div>
      <div className="match-header" aria-hidden="true"><span>Date</span><span>Group</span><span>Home</span><span>Score</span><span>Away</span><span>Model edge</span><span>Venue / status</span></div>
      <div className="match-list">
        {visibleMatches.map((match) => {
          const expanded = expandedId === match.id;
          const live = match.status === "in";
          const canShowPrediction = match.status !== "post";
          const details = match.details ?? {};
          const goals = details.goals ?? [];
          const timeline = details.events ?? [];
          const broadcasts = details.broadcasts ?? [];
          const predictionRows = [
            { label: match.home_team, value: match.prediction.home_win_probability },
            { label: "Draw", value: match.prediction.draw_probability },
            { label: match.away_team, value: match.prediction.away_win_probability },
          ];
          const modelLeader = [...predictionRows].sort((a, b) => b.value - a.value)[0];
          return <div className={expanded ? "match-row-wrap expanded" : "match-row-wrap"} key={match.id}>
            <button className="match-row" type="button" onClick={() => setExpandedId(expanded ? null : match.id)} aria-expanded={expanded}>
              <span><small>#{match.match_number}</small>{formatKickoff(match.kickoff)}</span><span>{match.group}</span><strong>{match.home_team}</strong><span className={live ? "score live" : "score"}>{match.status !== "pre" ? `${match.home_score} – ${match.away_score}` : "–"}</span><strong>{match.away_team}</strong><span className="match-edge">{canShowPrediction ? `${modelLeader.label} ${formatPercent(modelLeader.value)}` : "Final"}</span><span className={match.completed ? "status completed" : live ? "status live" : "status"}>{match.completed ? <CheckIcon /> : <ClockIcon />}<span><strong>{live ? "Live" : match.completed ? "Completed" : "Scheduled"}</strong><small>{live ? match.status_detail : match.venue}</small></span><ChevronIcon className={expanded ? "chevron open" : "chevron"} /></span>
            </button>
            {expanded ? <div className="match-details-panel">
              <div className="match-detail-grid">
                <div><span>Kickoff</span><strong>{formatLongKickoff(match.kickoff)}</strong></div>
                <div><span>Venue</span><strong>{details.venue_full_name || match.venue}</strong><small>{[details.venue_city, details.venue_country].filter(Boolean).join(", ")}</small></div>
                <div><span>Attendance</span><strong>{details.attendance ? details.attendance.toLocaleString() : "TBD"}</strong></div>
                <div><span>Broadcast</span><strong>{broadcasts.length ? broadcasts.join(", ") : "TBD"}</strong></div>
              </div>
              {canShowPrediction ? <div className="match-prediction-card">
                <div><strong>Model prediction</strong><span>Expected goals: {match.home_team} {match.prediction.home_expected_goals.toFixed(2)}, {match.away_team} {match.prediction.away_expected_goals.toFixed(2)}</span></div>
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
      </div>
      <p className="matches-note">Scores refresh automatically. Live scores are displayed immediately; standings, ratings, and tournament forecasts update only after the result is final.</p>
    </section>
  );
}
