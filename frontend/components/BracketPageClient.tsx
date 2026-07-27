"use client";

import { Header } from "@/components/Header";
import { formatDateTimeET } from "@/lib/format";
import type { BracketMatch, BracketProjection, BracketTeam } from "@/lib/types";

type Props = {
  initialBracket: BracketProjection | null;
  initialError?: string | null;
};

function formatPercent(value: number) {
  const percent = value * 100;
  if (percent === 0) return "0%";
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

function TeamLine({ team, probability, winner, showProbability }: { team: BracketTeam; probability: number; winner: boolean; showProbability: boolean }) {
  return (
    <div className={winner ? "bracket-team winner" : "bracket-team"}>
      <span><strong>{team.team}</strong><small>Group {team.group}</small></span>
      {showProbability ? <em>{formatPercent(probability)}</em> : null}
    </div>
  );
}

function MatchCard({ match, connectPair, showProbability }: { match: BracketMatch; connectPair: boolean; showProbability: boolean }) {
  const homeWins = match.projected_winner.team_id === match.home.team_id;
  const score = formatBracketScore(match);
  return (
    <article className={connectPair ? "bracket-match connector-pair" : "bracket-match"} data-match-id={match.match_number}>
      <div className="bracket-match-meta"><span>#{match.match_number}</span><span>{formatDateTimeET(match.kickoff)}</span>{score ? <em className="bracket-score">{score}</em> : null}</div>
      <TeamLine team={match.home} probability={match.home_advance_probability} winner={homeWins} showProbability={showProbability} />
      <TeamLine team={match.away} probability={match.away_advance_probability} winner={!homeWins} showProbability={showProbability} />
    </article>
  );
}

export function BracketPageClient({ initialBracket, initialError = null }: Props) {
  const bracket = initialBracket;
  const finalMatch = bracket?.rounds.find((round) => round.key === "final")?.matches[0];
  const tournamentComplete = finalMatch?.status === "post" && finalMatch.winner_status === "confirmed";
  const displayedFinalists = tournamentComplete && finalMatch
    ? [finalMatch.home, finalMatch.away]
    : bracket?.finalists ?? [];
  const displayedChampion = tournamentComplete && finalMatch
    ? finalMatch.projected_winner
    : bracket?.favorite;

  return (
    <>
      <Header />
      <main id="top">
        {initialError ? <div className="error-banner" role="alert"><strong>Something went wrong.</strong> {initialError}</div> : null}
        {bracket ? <section className="bracket-section" aria-labelledby="bracket-heading">
          <div className="bracket-hero">
            <div>
              <h1 id="bracket-heading">World Cup 2026 bracket</h1>
              <p>{tournamentComplete ? "The complete knockout bracket and final results." : "The current playoff tree uses the live group tables, FIFA third-place assignment rules, and the same match model that powers the forecast."}</p>
            </div>
            <div className="bracket-status">
              <span>{tournamentComplete ? "Champion" : "Predicted champion"}</span>
              <strong>{displayedChampion?.team}</strong>
              <small>{tournamentComplete ? "World Cup winner" : `${formatPercent(bracket.favorite.champion_probability)} cup chance`} · updated {formatDateTimeET(bracket.forecast.created_at)}</small>
            </div>
          </div>
          <div className="bracket-layout">
            <div className="bracket-board">
              {bracket.rounds.map((round) => (
                <div className="bracket-round" key={round.key}>
                  <h2>{round.label}</h2>
                  <div className="bracket-round-matches">{round.matches.map((match, index) => <MatchCard connectPair={round.key !== "final" && index % 2 === 0} match={match} showProbability={!tournamentComplete} key={match.match_number} />)}</div>
                </div>
              ))}
            </div>
            <aside className="bracket-insights" aria-label="Bracket insights">
              <div><span>{tournamentComplete ? "Champion" : "Cup favorite"}</span><strong>{displayedChampion?.team}</strong><small>{tournamentComplete ? "Final result confirmed" : `${formatPercent(bracket.favorite.champion_probability)} champion probability`}</small></div>
              <div><span>{tournamentComplete ? "Finalists" : "Most likely finalists"}</span>{displayedFinalists.map((team) => <p key={team.team_id}><strong>{team.team}</strong><small>{tournamentComplete ? (team.team_id === displayedChampion?.team_id ? "Champion" : "Runner-up") : formatPercent(team.final_probability)}</small></p>)}</div>
              {!tournamentComplete ? <div><span>Model note</span><small>Dates and kickoff times use FIFA&apos;s published match schedule and are shown in Eastern Time. Probabilities show the model edge to advance from each matchup.</small></div> : null}
            </aside>
          </div>

        </section> : null}
      </main>
    </>
  );
}
