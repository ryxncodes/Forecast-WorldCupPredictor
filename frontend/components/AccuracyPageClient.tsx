"use client";

import { useEffect, useState } from "react";
import type { AccuracyReport } from "@/lib/types";
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

export function AccuracyPageClient({ initialReport, initialError = null }: Props) {
  const [report, setReport] = useState(initialReport);
  const [error, setError] = useState<string | null>(initialError);
  const [loading, setLoading] = useState(false);

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
            <p>Each completed match is scored against the model state from immediately before that match was replayed into the ratings.</p>
          </div>
          <div className="page-actions">
            <button className="secondary-button" type="button" onClick={refresh} disabled={loading}><RefreshCwIcon className={loading ? "spinning" : ""} />Refresh</button>
          </div>
          {error ? <div className="error-banner">{error}</div> : null}
          {report ? <>
            <div className="accuracy-scorecards">
              <div><span>Result picks</span><strong>{percent(report.pick_accuracy)}</strong><small>{report.picked_correct}/{report.completed_matches} correct</small></div>
              <div><span>Brier score</span><strong>{number(report.average_brier_score)}</strong><small>Lower is better</small></div>
              <div><span>Log loss</span><strong>{number(report.average_log_loss)}</strong><small>Lower is better</small></div>
              <div><span>Exact scores</span><strong>{percent(report.exact_score_rate)}</strong><small>{report.exact_scores}/{report.completed_matches} hit</small></div>
              <div><span>Goal error</span><strong>{number(report.average_goal_error)}</strong><small>Average combined xG miss</small></div>
            </div>
            <div className="accuracy-table-wrap">
              <table className="accuracy-table">
                <thead><tr><th>Match</th><th>Prediction</th><th>Actual</th><th>Most likely score</th><th>xG</th><th>Brier</th><th>Log loss</th></tr></thead>
                <tbody>{report.matches.map((match) => (
                  <tr key={match.match_id}>
                    <td><strong>#{match.match_number} · Group {match.group}</strong><span>{formatKickoff(match.kickoff)}</span><small>{match.home_team} vs {match.away_team}</small></td>
                    <td><span className={match.picked_correct ? "accuracy-chip correct" : "accuracy-chip wrong"}>{match.picked_correct ? "Right" : "Wrong"}</span><strong>{match.predicted_outcome_label}</strong><small>{percent(Math.max(match.home_win_probability, match.draw_probability, match.away_win_probability))}</small></td>
                    <td><strong>{match.home_score}-{match.away_score}</strong><small>{match.actual_outcome_label}</small></td>
                    <td><strong>{match.predicted_home_score}-{match.predicted_away_score}</strong><small>{percent(match.predicted_score_probability, 1)} scoreline chance</small></td>
                    <td><strong>{number(match.home_expected_goals)}-{number(match.away_expected_goals)}</strong><small>{number(match.goal_error)} goal error</small></td>
                    <td>{number(match.brier_score)}</td>
                    <td>{number(match.log_loss)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </> : null}
        </section>
      </main>
    </>
  );
}
