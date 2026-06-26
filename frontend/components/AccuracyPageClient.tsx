"use client";

import { Fragment, useEffect, useState } from "react";
import type { AccuracyMatch, AccuracyReport } from "@/lib/types";
import { loadAccuracy } from "@/lib/api";
import { Header } from "./Header";
import { RefreshCwIcon } from "./Icons";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

type Props = {
  initialReport: AccuracyReport | null;
  initialError?: string | null;
};

function percent(value: number, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

function scoredPercent(value: number, scored: number) {
  return scored ? percent(value) : "-";
}

function number(value: number, digits = 2) {
  return value.toFixed(digits);
}

function formatKickoff(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function predictionRows(match: AccuracyMatch) {
  return [
    { label: match.home_team, value: match.home_win_probability },
    { label: "Draw", value: match.draw_probability },
    { label: match.away_team, value: match.away_win_probability },
  ];
}

const outcomeLabels = [
  ["home", "Home wins"],
  ["draw", "Draws"],
  ["away", "Away wins"],
] as const;

function DistributionBars({ report }: { report: AccuracyReport }) {
  const maxCount = Math.max(
    1,
    ...outcomeLabels.flatMap(([key]) => [
      report.predicted_result_distribution[key],
      report.actual_result_distribution[key],
    ]),
  );
  return (
    <div className="accuracy-distribution-bars">
      {outcomeLabels.map(([key, label]) => {
        const predicted = report.predicted_result_distribution[key];
        const actual = report.actual_result_distribution[key];
        return <div className="accuracy-distribution-bar-row" key={key}>
          <strong>{label}</strong>
          <div><span>Predicted</span><em><i style={{ width: `${(predicted / maxCount) * 100}%` }} /></em><b>{predicted}</b></div>
          <div><span>Actual</span><em><i style={{ width: `${(actual / maxCount) * 100}%` }} /></em><b>{actual}</b></div>
        </div>;
      })}
    </div>
  );
}

export function AccuracyPageClient({ initialReport, initialError = null }: Props) {
  const [report, setReport] = useState(initialReport);
  const [error, setError] = useState<string | null>(initialError);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      setReport(await loadAccuracy());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not refresh model accuracy");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setReport(initialReport);
    setError(initialError);
  }, [initialReport, initialError]);

  useAutoRefresh(refresh, 180000);

  return (
    <>
      <Header />
      <main>
        <section className="accuracy-section" aria-labelledby="accuracy-heading">
          <div className="history-heading">
            <h1 id="accuracy-heading">Model accuracy</h1>
            <p>Earlier matches keep the historical replay estimate; new matches use locked pre-kickoff snapshots. The displayed pick is the highest of home win, draw, and away win.</p>
          </div>
          <div className="page-actions">
            <button className="secondary-button" type="button" onClick={refresh} disabled={loading}><RefreshCwIcon className={loading ? "spinning" : ""} />Refresh</button>
          </div>
          {error ? <div className="error-banner">{error}</div> : null}
          {report ? <>
            <div className="accuracy-scorecards">
              <div><span>Top-pick result accuracy</span><strong>{scoredPercent(report.pick_accuracy, report.scored_matches)}</strong><small>{report.picked_correct}/{report.scored_matches} correct</small></div>
              <div><span>Scored matches</span><strong>{report.scored_matches}</strong><small>{report.locked_predictions} locked · {report.backfilled_predictions} backfilled{report.unscored_completed_matches ? ` · ${report.unscored_completed_matches} unscored` : ""}</small></div>
              <div><span>Brier score</span><strong>{number(report.average_brier_score)}</strong><small>Lower is better</small></div>
              <div><span>Log loss</span><strong>{number(report.average_log_loss)}</strong><small>Lower is better</small></div>
              <div><span>Exact scores</span><strong>{scoredPercent(report.exact_score_rate, report.scored_matches)}</strong><small>{report.exact_scores}/{report.scored_matches} hit</small></div>
            </div>
            <p className="accuracy-note">Top-pick accuracy scores only the single highest-probability result. The model still estimates home, draw, and away probabilities; Brier score and log loss evaluate that full probability distribution.</p>
            <div className="accuracy-summary-grid">
              <section aria-labelledby="distribution-heading">
                <h2 id="distribution-heading">Result distribution</h2>
                <DistributionBars report={report} />
                <div className="accuracy-distribution compact">
                  <div><span>Outcome</span><span>Predicted</span><span>Actual</span></div>
                  {outcomeLabels.map(([key, label]) => <div key={key}><strong>{label}</strong><span>{report.predicted_result_distribution[key]}</span><span>{report.actual_result_distribution[key]}</span></div>)}
                </div>
              </section>
              <section aria-labelledby="quality-heading">
                <h2 id="quality-heading">Scoring quality</h2>
                <div className="accuracy-insight-grid">
                  <div><span>Mean goal error</span><strong>{number(report.average_goal_error)}</strong><small>Total home plus away xG error per match</small></div>
                  <div><span>Exact-score misses</span><strong>{report.scored_matches - report.exact_scores}</strong><small>{report.exact_scores}/{report.scored_matches} exact scorelines hit</small></div>
                  <div><span>Unscored finals</span><strong>{report.unscored_completed_matches}</strong><small>Completed matches missing a prediction snapshot</small></div>
                </div>
              </section>
              <section aria-labelledby="latest-heading">
                <h2 id="latest-heading">Latest scored</h2>
                <div className="accuracy-latest-list">
                  {report.matches.slice(0, 4).map((match) => <button type="button" key={match.match_id} onClick={() => setExpandedId(match.match_id)}>
                    <span>#{match.match_number} · {formatKickoff(match.kickoff)}</span>
                    <strong>{match.home_team} {match.home_score}-{match.away_score} {match.away_team}</strong>
                    <small>{match.picked_correct ? "Right" : "Wrong"} · picked {match.predicted_outcome_label}</small>
                  </button>)}
                </div>
              </section>
            </div>
            {report.matches.length ? <div className="accuracy-table-wrap">
              <table className="accuracy-table">
                <thead><tr><th>Match</th><th>Prediction</th><th>Actual</th><th>Most likely score</th><th>xG</th><th>Brier</th><th>Log loss</th></tr></thead>
                <tbody>{report.matches.map((match) => {
                  const expanded = expandedId === match.match_id;
                  return <Fragment key={match.match_id}>
                    <tr className={expanded ? "accuracy-row expanded" : "accuracy-row"}>
                      <td><button className="accuracy-match-toggle" type="button" onClick={() => setExpandedId(expanded ? null : match.match_id)} aria-expanded={expanded}><strong>#{match.match_number} · Group {match.group}</strong><span>{formatKickoff(match.kickoff)}</span><small>{match.home_team} vs {match.away_team}</small></button></td>
                      <td><span className={match.picked_correct ? "accuracy-chip correct" : "accuracy-chip wrong"}>{match.picked_correct ? "Right" : "Wrong"}</span><strong>{match.predicted_outcome_label}</strong><small>{percent(Math.max(match.home_win_probability, match.draw_probability, match.away_win_probability))} · {match.prediction_source}</small></td>
                      <td><strong>{match.home_score}-{match.away_score}</strong><small>{match.actual_outcome_label}</small></td>
                      <td><strong>{match.predicted_home_score}-{match.predicted_away_score}</strong><small>{percent(match.predicted_score_probability, 1)} scoreline chance</small></td>
                      <td><strong>{number(match.home_expected_goals)}-{number(match.away_expected_goals)}</strong><small>{number(match.goal_error)} goal error</small></td>
                      <td>{number(match.brier_score)}</td>
                      <td>{number(match.log_loss)}</td>
                    </tr>
                    {expanded ? <tr className="accuracy-detail-row"><td colSpan={7}>
                      <div className="match-prediction-card accuracy-prediction-card">
                        <div><strong>Outcome probabilities</strong><span>Expected goals: {match.home_team} {number(match.home_expected_goals)}, {match.away_team} {number(match.away_expected_goals)}</span></div>
                        <div className="match-prediction-bars">{predictionRows(match).map((row) => <div key={row.label}><span>{row.label}</span><strong>{percent(row.value)}</strong><em><i style={{ width: `${row.value * 100}%` }} /></em></div>)}</div>
                      </div>
                    </td></tr> : null}
                  </Fragment>;
                })}</tbody>
              </table>
            </div> : <div className="history-empty"><strong>No scored predictions yet.</strong><span>Future locked predictions will appear here after the final score is known.</span></div>}
          </> : null}
        </section>
      </main>
    </>
  );
}
