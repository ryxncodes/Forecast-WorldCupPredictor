"use client";

import { Fragment, useState } from "react";
import type { AccuracyMatch, AccuracyReport, KnockoutAccuracyMatch } from "@/lib/types";
import { formatDateTimeET } from "@/lib/format";
import { Header } from "./Header";

type Props = {
  initialReport: AccuracyReport | null;
  initialError?: string | null;
};

function percent(value: number, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

function scoredPercent(correct: number, total: number) {
  return total ? percent(correct / total) : "-";
}

function predictionRows(match: AccuracyMatch) {
  return [
    { label: match.home_team, value: match.home_win_probability },
    { label: "Draw", value: match.draw_probability },
    { label: match.away_team, value: match.away_win_probability },
  ];
}

function knockoutStatus(match: KnockoutAccuracyMatch) {
  return match.picked_correct ? "Right" : "Wrong";
}

export function AccuracyPageClient({ initialReport, initialError = null }: Props) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const report = initialReport;
  const groupMatches = report?.matches ?? [];
  const groupCorrect = groupMatches.filter((match) => match.picked_correct).length;
  const groupExact = groupMatches.filter((match) => match.exact_score).length;
  const knockoutMatches = report?.knockout_predictions?.matches ?? [];
  const knockoutCorrect = knockoutMatches.filter((match) => match.picked_correct).length;
  const knockoutExact = knockoutMatches.filter((match) => match.exact_score).length;

  return (
    <>
      <Header />
      <main>
        <section className="accuracy-section" aria-labelledby="accuracy-heading">
          <div className="history-heading">
            <h1 id="accuracy-heading">Prediction results</h1>
            <p>How the model&apos;s predictions performed across the tournament.</p>
          </div>
          {initialError ? <div className="error-banner" role="alert">{initialError}</div> : null}
          {report ? <>
            <div className="accuracy-scorecards compact-results">
              <div><span>Group-stage accuracy</span><strong>{scoredPercent(groupCorrect, groupMatches.length)}</strong><small>{groupCorrect}/{groupMatches.length} correct</small></div>
              <div><span>Exact scores</span><strong>{scoredPercent(groupExact, groupMatches.length)}</strong><small>{groupExact}/{groupMatches.length} exact</small></div>
              <div><span>Matches scored</span><strong>{groupMatches.length}</strong><small>Group-stage matches</small></div>
            </div>

            <section className="accuracy-knockout-section" aria-labelledby="knockout-accuracy-heading">
              <div className="history-heading">
                <h2 id="knockout-accuracy-heading">Knockout predictions</h2>
              </div>
              <div className="accuracy-scorecards compact-results">
                <div><span>Knockout accuracy</span><strong>{scoredPercent(knockoutCorrect, knockoutMatches.length)}</strong><small>{knockoutCorrect}/{knockoutMatches.length} correct</small></div>
                <div><span>Exact scores</span><strong>{scoredPercent(knockoutExact, knockoutMatches.length)}</strong><small>{knockoutExact}/{knockoutMatches.length} exact</small></div>
                <div><span>Matches scored</span><strong>{knockoutMatches.length}</strong><small>Knockout matches</small></div>
              </div>
              {knockoutMatches.length ? <div className="accuracy-table-wrap">
                <table className="accuracy-table knockout-accuracy-table simplified">
                  <thead><tr><th>Match</th><th>Prediction</th><th>Result</th><th>Predicted score</th></tr></thead>
                  <tbody>{knockoutMatches.map((match) => <tr className="accuracy-row" key={match.snapshot_id}>
                    <td><strong>#{match.match_number} · {match.round_label}</strong><span>{formatDateTimeET(match.kickoff)}</span><small>{match.home_team} vs {match.away_team}</small></td>
                    <td><span className={match.picked_correct ? "accuracy-chip correct" : "accuracy-chip wrong"}>{knockoutStatus(match)}</span><strong>{match.predicted_advancer}</strong><small>{match.home_team} {percent(match.home_advance_probability)} · {match.away_team} {percent(match.away_advance_probability)}</small></td>
                    <td><strong>{match.home_score}-{match.away_score}</strong><small>{match.actual_advancer} advanced</small></td>
                    <td><strong>{match.predicted_home_score}-{match.predicted_away_score}</strong><small>{percent(match.predicted_score_probability)} chance</small></td>
                  </tr>)}</tbody>
                </table>
              </div> : null}
            </section>

            <h2>Group-stage predictions</h2>
            {groupMatches.length ? <div className="accuracy-table-wrap">
              <table className="accuracy-table simplified">
                <thead><tr><th>Match</th><th>Prediction</th><th>Result</th><th>Predicted score</th></tr></thead>
                <tbody>{groupMatches.map((match) => {
                  const expanded = expandedId === match.match_id;
                  return <Fragment key={match.match_id}>
                    <tr className={expanded ? "accuracy-row expanded" : "accuracy-row"}>
                      <td><button className="accuracy-match-toggle" type="button" onClick={() => setExpandedId(expanded ? null : match.match_id)} aria-expanded={expanded}><strong>#{match.match_number} · Group {match.group}</strong><span>{formatDateTimeET(match.kickoff)}</span><small>{match.home_team} vs {match.away_team}</small></button></td>
                      <td><span className={match.picked_correct ? "accuracy-chip correct" : "accuracy-chip wrong"}>{match.picked_correct ? "Right" : "Wrong"}</span><strong>{match.predicted_outcome_label}</strong><small>{percent(Math.max(match.home_win_probability, match.draw_probability, match.away_win_probability))}</small></td>
                      <td><strong>{match.home_score}-{match.away_score}</strong><small>{match.actual_outcome_label}</small></td>
                      <td><strong>{match.predicted_home_score}-{match.predicted_away_score}</strong><small>{percent(match.predicted_score_probability)} chance</small></td>
                    </tr>
                    {expanded ? <tr className="accuracy-detail-row"><td colSpan={4}>
                      <div className="match-prediction-card accuracy-prediction-card">
                        <strong>Outcome probabilities</strong>
                        <div className="match-prediction-bars">{predictionRows(match).map((row) => <div key={row.label}><span>{row.label}</span><strong>{percent(row.value)}</strong><em><i style={{ width: `${row.value * 100}%` }} /></em></div>)}</div>
                      </div>
                    </td></tr> : null}
                  </Fragment>;
                })}</tbody>
              </table>
            </div> : null}
          </> : null}
        </section>
      </main>
    </>
  );
}
