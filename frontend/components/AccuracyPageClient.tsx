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

function points(value: number, digits = 1) {
  return `${(value * 100).toFixed(digits)} pts`;
}

function signedPoints(value: number, digits = 1) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${points(value, digits)}`;
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
              <div><span>1X2 top-pick accuracy</span><strong>{scoredPercent(report.pick_accuracy, report.scored_matches)}</strong><small>{report.picked_correct}/{report.scored_matches} correct</small></div>
              <div><span>Scored matches</span><strong>{report.scored_matches}</strong><small>{report.locked_predictions} locked · {report.backfilled_predictions} backfilled{report.unscored_completed_matches ? ` · ${report.unscored_completed_matches} unscored` : ""}</small></div>
              <div><span>Brier score</span><strong>{number(report.average_brier_score)}</strong><small>Lower is better</small></div>
              <div><span>Log loss</span><strong>{number(report.average_log_loss)}</strong><small>Lower is better</small></div>
              <div><span>Exact scores</span><strong>{scoredPercent(report.exact_score_rate, report.scored_matches)}</strong><small>{report.exact_scores}/{report.scored_matches} hit</small></div>
            </div>
            <p className="accuracy-note">1X2 means the model can choose home win, draw, or away win as the predicted result. Probability metrics such as Brier score and log loss evaluate the full probability distribution, while top-pick accuracy only checks whether the single highest-probability outcome matched the result.</p>
            <div className="accuracy-debug-grid">
              <section aria-labelledby="distribution-heading">
                <h2 id="distribution-heading">Result distribution</h2>
                <div className="accuracy-distribution">
                  <div><span>Outcome</span><span>Predicted</span><span>Actual</span></div>
                  {outcomeLabels.map(([key, label]) => <div key={key}><strong>{label}</strong><span>{report.predicted_result_distribution[key]}</span><span>{report.actual_result_distribution[key]}</span></div>)}
                </div>
              </section>
              <section aria-labelledby="draw-diagnostics-heading">
                <h2 id="draw-diagnostics-heading">Draw diagnostics</h2>
                <div className="accuracy-diagnostic-stats">
                  <div><span>Highest draw probability</span><strong>{percent(report.draw_diagnostics.highest_draw_probability)}</strong></div>
                  <div><span>Average draw probability</span><strong>{percent(report.draw_diagnostics.average_draw_probability)}</strong></div>
                  <div><span>Median draw probability</span><strong>{percent(report.draw_diagnostics.median_draw_probability)}</strong></div>
                  <div><span>Draw second-highest</span><strong>{report.draw_diagnostics.draw_second_highest_count}</strong></div>
                  <div><span>Within 1 point</span><strong>{report.draw_diagnostics.draw_within_1_point_count}</strong></div>
                  <div><span>Within 3 points</span><strong>{report.draw_diagnostics.draw_within_3_points_count}</strong></div>
                  <div><span>Within 5 points</span><strong>{report.draw_diagnostics.draw_within_5_points_count}</strong></div>
                  <div><span>Draw highest</span><strong>{report.draw_diagnostics.draw_highest_count}</strong></div>
                </div>
              </section>
            </div>
            <div className="accuracy-debug-grid">
              <section aria-labelledby="draw-classification-heading">
                <h2 id="draw-classification-heading">Draw classification</h2>
                <div className="accuracy-diagnostic-stats compact">
                  <div><span>Draw precision</span><strong>{percent(report.draw_diagnostics.draw_precision)}</strong></div>
                  <div><span>Draw recall</span><strong>{percent(report.draw_diagnostics.draw_recall)}</strong></div>
                  <div><span>Draw F1</span><strong>{percent(report.draw_diagnostics.draw_f1)}</strong></div>
                  <div><span>Predicted draws</span><strong>{report.draw_diagnostics.predicted_draws}</strong></div>
                  <div><span>Actual draws</span><strong>{report.draw_diagnostics.actual_draws}</strong></div>
                  <div><span>Predicted draw hits</span><strong>{report.draw_diagnostics.true_predicted_draws}</strong></div>
                </div>
                {report.draw_diagnostics.predicted_draws === 0 ? <p className="accuracy-note">No matches were top-picked as draws, so draw precision and F1 are shown as 0 while the probability calibration tables below still evaluate draw probability quality.</p> : null}
              </section>
              <section aria-labelledby="neutral-bias-heading">
                <h2 id="neutral-bias-heading">Neutral-site listed-team check</h2>
                <div className="accuracy-table-wrap">
                  <table className="accuracy-table accuracy-compact-table">
                    <thead><tr><th>Outcome</th><th>Avg predicted</th><th>Actual rate</th><th>Top-pick rate</th></tr></thead>
                    <tbody>{outcomeLabels.map(([key, label]) => {
                      const row = report.neutral_site_bias_check[key];
                      return <tr key={`bias-${key}`}><td><strong>{label}</strong><span>{row.actual_count} actual · {row.top_pick_count} picked</span></td><td>{percent(row.average_predicted_probability)}</td><td>{percent(row.actual_frequency)}</td><td>{percent(row.top_pick_rate)}</td></tr>;
                    })}</tbody>
                  </table>
                </div>
                <p className="accuracy-note">{report.home_field_advantage.detail}</p>
              </section>
            </div>
            <section className="accuracy-section" aria-labelledby="draw-calibration-heading">
              <h2 id="draw-calibration-heading">Draw probability calibration</h2>
              <div className="accuracy-table-wrap">
                <table className="accuracy-table accuracy-compact-table">
                  <thead><tr><th>Draw probability bucket</th><th>Matches</th><th>Avg predicted draw</th><th>Actual draw rate</th><th>Actual minus predicted</th></tr></thead>
                  <tbody>{report.draw_calibration_buckets.map((bucket) => <tr key={bucket.bucket}>
                    <td><strong>{bucket.bucket}</strong></td>
                    <td>{bucket.matches}</td>
                    <td>{bucket.matches ? percent(bucket.average_predicted_probability) : "-"}</td>
                    <td>{bucket.matches ? percent(bucket.actual_frequency) : "-"}</td>
                    <td>{bucket.matches ? signedPoints(bucket.difference) : "-"}</td>
                  </tr>)}</tbody>
                </table>
              </div>
            </section>
            <section className="accuracy-section" aria-labelledby="outcome-calibration-heading">
              <h2 id="outcome-calibration-heading">Outcome probability calibration</h2>
              <div className="accuracy-calibration-grid">
                {outcomeLabels.map(([key, label]) => <div className="accuracy-table-wrap" key={`calibration-${key}`}>
                  <table className="accuracy-table accuracy-compact-table">
                    <caption>{label}</caption>
                    <thead><tr><th>Bucket</th><th>Matches</th><th>Avg predicted</th><th>Actual freq.</th></tr></thead>
                    <tbody>{report.outcome_calibration_buckets[key].filter((bucket) => bucket.matches > 0).map((bucket) => <tr key={`${key}-${bucket.bucket}`}>
                      <td><strong>{bucket.bucket}</strong></td>
                      <td>{bucket.matches}</td>
                      <td>{percent(bucket.average_predicted_probability)}</td>
                      <td>{percent(bucket.actual_frequency)}</td>
                    </tr>)}</tbody>
                  </table>
                </div>)}
              </div>
            </section>
            {report.draw_diagnostic_matches.length ? <section className="accuracy-section" aria-labelledby="draw-margin-heading">
              <h2 id="draw-margin-heading">Draw margin report</h2>
              <p className="accuracy-note">Sorted by smallest draw margin from the top non-draw class.</p>
              <div className="accuracy-table-wrap">
                <table className="accuracy-table accuracy-debug-table">
                  <thead><tr><th>Match</th><th>Actual</th><th>Home win</th><th>Draw</th><th>Away win</th><th>Selected</th><th>Correct</th><th>Draw rank</th><th>Draw margin</th></tr></thead>
                  <tbody>{report.draw_diagnostic_matches.map((match) => <tr key={`draw-${match.match_id}`}>
                    <td><strong>#{match.match_number}</strong><span>{match.home_team} vs {match.away_team}</span></td>
                    <td><strong>{match.actual_outcome_label}</strong><span>{match.home_score}-{match.away_score}</span></td>
                    <td>{percent(match.home_win_probability)}</td>
                    <td>{percent(match.draw_probability)}</td>
                    <td>{percent(match.away_win_probability)}</td>
                    <td><strong>{match.predicted_outcome_label}</strong><span>{match.stored_pick_matches_argmax ? "Stored argmax ok" : `Stored ${match.stored_predicted_outcome}`}</span></td>
                    <td><span className={match.picked_correct ? "accuracy-chip correct" : "accuracy-chip wrong"}>{match.picked_correct ? "Right" : "Wrong"}</span></td>
                    <td>{match.draw_rank}</td>
                    <td>{points(match.draw_margin_from_top)}</td>
                  </tr>)}</tbody>
                </table>
              </div>
            </section> : null}
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
                        <div><strong>1X2 probabilities</strong><span>Expected goals: {match.home_team} {number(match.home_expected_goals)}, {match.away_team} {number(match.away_expected_goals)}</span></div>
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
