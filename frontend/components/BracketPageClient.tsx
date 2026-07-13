"use client";

import { useCallback, useState } from "react";
import { Header } from "@/components/Header";
import { loadBracket } from "@/lib/api";
import { formatDateTimeET } from "@/lib/format";
import { useAutoRefresh } from "@/lib/useAutoRefresh";
import type { BracketMatch, BracketProjection, BracketTeam } from "@/lib/types";

type Props = {
  initialBracket: BracketProjection | null;
  initialError?: string | null;
};

function formatPercent(value: number) {
  const percent = value * 100;
  if (percent < 1) return `${percent.toFixed(1)}%`;
  return `${Math.round(percent)}%`;
}

function formatBracketScore(match: BracketMatch) {
  if (match.home_score == null || match.away_score == null) return null;
  if (match.home_shootout_score != null || match.away_shootout_score != null) {
    return `${match.home_score} (${match.home_shootout_score ?? 0}) – ${match.away_score} (${match.away_shootout_score ?? 0})`;
  }
  return `${match.home_score} – ${match.away_score}`;
}

function TeamLine({ team, probability, winner }: { team: BracketTeam; probability: number; winner: boolean }) {
  return (
    <div className={winner ? "bracket-team winner" : "bracket-team"}>
      <span><strong>{team.team}</strong><small>Group {team.group}</small></span>
      <em>{formatPercent(probability)}</em>
    </div>
  );
}

function MatchCard({ match, connectPair }: { match: BracketMatch; connectPair: boolean }) {
  const homeWins = match.projected_winner.team_id === match.home.team_id;
  const score = formatBracketScore(match);
  return (
    <article className={connectPair ? "bracket-match connector-pair" : "bracket-match"} data-match-id={match.match_number}>
      <div className="bracket-match-meta"><span>#{match.match_number}</span><span>{formatDateTimeET(match.kickoff)}</span>{score ? <em className="bracket-score">{score}</em> : null}</div>
      <TeamLine team={match.home} probability={match.home_advance_probability} winner={homeWins} />
      <TeamLine team={match.away} probability={match.away_advance_probability} winner={!homeWins} />
    </article>
  );
}

export function BracketPageClient({ initialBracket, initialError = null }: Props) {
  const [bracket, setBracket] = useState<BracketProjection | null>(initialBracket);
  const [error, setError] = useState<string | null>(initialError);

  const refresh = useCallback(async () => {
    try {
      setBracket(await loadBracket());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load bracket projection");
    }
  }, []);

  useAutoRefresh(refresh, 180000);

  return (
    <>
      <Header simulations={bracket?.forecast.simulations ?? 10_000} />
      <main id="top">
        {error ? <div className="error-banner" role="alert"><strong>Something went wrong.</strong> {error} <button onClick={refresh}>Try again</button></div> : null}
        {!bracket ? <div className="loading-state"><span className="spinner spinning" /><p>Loading the bracket…</p></div> : null}
        {bracket ? <section className="bracket-section" aria-labelledby="bracket-heading">
          <div className="bracket-hero">
            <div>
              <h1 id="bracket-heading">World Cup 2026 bracket</h1>
              <p>The current playoff tree uses the live group tables, FIFA third-place assignment rules, and the same match model that powers the forecast.</p>
            </div>
            <div className="bracket-status">
              <span>Predicted champion</span>
              <strong>{bracket.favorite.team}</strong>
              <small>{formatPercent(bracket.favorite.champion_probability)} cup chance · updated {formatDateTimeET(bracket.forecast.created_at)}</small>
            </div>
          </div>
          <div className="bracket-layout">
            <div className="bracket-board">
              {bracket.rounds.map((round) => (
                <div className="bracket-round" key={round.key}>
                  <h2>{round.label}</h2>
                  <div className="bracket-round-matches">{round.matches.map((match, index) => <MatchCard connectPair={round.key !== "final" && index % 2 === 0} match={match} key={match.match_number} />)}</div>
                </div>
              ))}
            </div>
            <aside className="bracket-insights" aria-label="Bracket insights">
              <div><span>Cup favorite</span><strong>{bracket.favorite.team}</strong><small>{formatPercent(bracket.favorite.champion_probability)} champion probability</small></div>
              <div><span>Most likely finalists</span>{bracket.finalists.map((team) => <p key={team.team_id}><strong>{team.team}</strong><small>{formatPercent(team.final_probability)}</small></p>)}</div>
              <div><span>Model note</span><small>Dates and kickoff times use FIFA's published match schedule and are shown in Eastern Time. Probabilities show the model edge to advance from each matchup.</small></div>
            </aside>
          </div>
          <p className="bracket-footnote">Dates and kickoff times shown in ET from FIFA's published match schedule. Probabilities show the model edge to advance from that matchup.</p>
        </section> : null}
      </main>
    </>
  );
}
