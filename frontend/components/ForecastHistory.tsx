"use client";

import { useMemo, useState } from "react";
import type { CSSProperties } from "react";
import type { Forecast, Match, ProbabilityKey } from "@/lib/types";

const WIDTH = 700;
const HEIGHT = 190;
const AXIS_LEFT = 44;
const POINT_INSET = 86;
const PLOT_TOP = 18;
const PLOT_BOTTOM = 24;

type DisplayRun = {
  run: Forecast;
  label: string;
};

const STAGE_LABELS: Record<string, string> = {
  round_of_32: "R32",
  round_of_16: "R16",
  quarterfinal: "QF",
  semifinal: "SF",
  third_place: "3rd",
  final: "Final",
};

function teamMilestones(
  orderedRuns: Forecast[],
  matches: Match[],
  teamId: number,
  metric: Extract<ProbabilityKey, "advance_probability" | "champion_probability">,
): DisplayRun[] {
  const completed = [...matches]
    .filter((match) => match.completed)
    .sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff) || a.match_number - b.match_number);
  const resultNumber = new Map(completed.map((match, index) => [match.match_number, index + 1]));
  const teamMatches = completed.filter((match) =>
    (match.home_team_id === teamId || match.away_team_id === teamId)
    && (metric === "champion_probability" || match.stage === "group")
  );
  const runsByProgress = [...orderedRuns].sort((a, b) =>
    a.completed_results - b.completed_results || Date.parse(b.created_at) - Date.parse(a.created_at)
  );
  const baseline = runsByProgress.find((run) => run.completed_results === 0) ?? runsByProgress[0];
  const points: DisplayRun[] = baseline
    ? [{ run: baseline, label: baseline.completed_results === 0 ? "Pre-tournament" : baseline.label }]
    : [];
  let groupMatchday = 0;
  for (const match of teamMatches) {
    if (match.stage === "group") groupMatchday += 1;
    const target = resultNumber.get(match.match_number);
    if (!target) continue;
    const run = runsByProgress.find((candidate) => candidate.completed_results >= target);
    if (!run) continue;
    const stage = match.stage === "group" ? `MD${groupMatchday}` : (STAGE_LABELS[match.stage] ?? match.stage);
    points.push({ run, label: `${stage} · ${match.home_team} ${match.home_score}–${match.away_score} ${match.away_team}` });
  }
  return points;
}

export function ForecastHistory({ runs, matches }: { runs: Forecast[]; matches: Match[] }) {
  const latest = runs[0];
  const defaultTeam = latest?.probabilities[0]?.team_id ?? 1;
  const [teamId, setTeamId] = useState(defaultTeam);
  const [metric, setMetric] = useState<Extract<ProbabilityKey, "advance_probability" | "champion_probability">>("advance_probability");
  const [hoveredPoint, setHoveredPoint] = useState<number | null>(null);
  const ordered = useMemo(() => [...runs].reverse(), [runs]);
  const displayRuns = useMemo(
    () => teamMilestones(ordered, matches, teamId, metric),
    [matches, metric, ordered, teamId],
  );
  const values = displayRuns.map(({ run, label }) => {
    const row = run.probabilities.find((candidate) => candidate.team_id === teamId);
    return { probability: row?.[metric] ?? 0, run, label };
  });
  const maximumPercent = Math.max(...values.map((point) => point.probability * 100), 0);
  const tickStep = maximumPercent <= 40 ? 10 : 20;
  const yMaximum = Math.min(100, Math.max(tickStep, Math.ceil(maximumPercent / tickStep) * tickStep));
  const ticks = Array.from({ length: yMaximum / tickStep + 1 }, (_, index) => index * tickStep);
  const points = values.map(({ probability, run }, index) => {
    const x = POINT_INSET + (index * (WIDTH - POINT_INSET * 2)) / Math.max(displayRuns.length - 1, 1);
    const y = HEIGHT - PLOT_BOTTOM - (probability * 100 / yMaximum) * (HEIGHT - PLOT_TOP - PLOT_BOTTOM);
    return { x, y, probability, run, label: values[index].label };
  });
  const line = points.map((point) => `${point.x},${point.y}`).join(" ");
  const denseChart = points.length > 16;
  const tooltipEdge = hoveredPoint === null
    ? ""
    : points[hoveredPoint].x / WIDTH < 0.35
      ? " edge-start"
      : points[hoveredPoint].x / WIDTH > 0.65
        ? " edge-end"
        : "";
  const selectedName = latest?.probabilities.find((row) => row.team_id === teamId)?.team ?? "Team";
  const countries = useMemo(
    () => [...(latest?.probabilities ?? [])].sort((a, b) => a.team.localeCompare(b.team)),
    [latest],
  );
  const metricLabel = metric === "advance_probability" ? "advance" : "win the tournament";

  if (!latest) return null;

  return (
    <section id="history" className="history-section" aria-labelledby="history-heading">
      <div className="history-heading">
        <div><h1 id="history-heading">Prediction history</h1><p>Follow how each country’s forecast changed after its own matches. Advance ends with Matchday 3; Champion continues through every knockout match that country played.</p></div>
      </div>
      <div className="history-workspace">
        <aside className="history-team-panel" aria-label="Choose a country">
          <strong>Countries</strong>
          <div className="history-team-list">{countries.map((row) => {
            const selected = row.team_id === teamId;
            return <button aria-pressed={selected} className={selected ? "selected" : ""} type="button" key={row.team_id} onClick={() => setTeamId(row.team_id)}><span>{row.team}</span><small>{Math.round(row[metric] * 100)}%</small></button>;
          })}</div>
        </aside>
        <div className="history-detail">
          <div className="history-detail-heading">
            <div><span className="eyebrow">Selected country</span><h2>{selectedName}</h2></div>
            <div className="history-controls">
              <div className="history-metric-toggle" aria-label="Choose probability"><button aria-pressed={metric === "advance_probability"} className={metric === "advance_probability" ? "active" : ""} type="button" onClick={() => { setMetric("advance_probability"); setHoveredPoint(null); }}>Advance</button><button aria-pressed={metric === "champion_probability"} className={metric === "champion_probability" ? "active" : ""} type="button" onClick={() => { setMetric("champion_probability"); setHoveredPoint(null); }}>Champion</button></div>
            </div>
          </div>
          {runs.length === 1 ? <div className="history-empty"><strong>The first snapshot is saved.</strong><span>The chart will grow after the next completed match and automatic refresh.</span></div> : <>
            <div className={denseChart ? "history-chart dense" : "history-chart"} role="img" aria-label={`${selectedName} probability to ${metricLabel} across ${points.length} displayed forecast snapshots`}>
              {ticks.map((tick) => {
                const y = HEIGHT - PLOT_BOTTOM - (tick / yMaximum) * (HEIGHT - PLOT_TOP - PLOT_BOTTOM);
                return <span className="history-y-label" key={tick} style={{ top: `${(y / HEIGHT) * 100}%` }}>{tick}%</span>;
              })}
              <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none">
                {ticks.map((tick) => {
                  const y = HEIGHT - PLOT_BOTTOM - (tick / yMaximum) * (HEIGHT - PLOT_TOP - PLOT_BOTTOM);
                  return <line className="history-grid-line" key={tick} x1={AXIS_LEFT} y1={y} x2={WIDTH - AXIS_LEFT} y2={y} />;
                })}
                <line className="history-axis-line" x1={AXIS_LEFT} y1={PLOT_TOP} x2={AXIS_LEFT} y2={HEIGHT - PLOT_BOTTOM} />
                <polyline points={line} />
                {points.map((point, index) => <circle aria-label={`${point.label}: ${(point.probability * 100).toFixed(1)}%`} className="history-point" key={`${point.run.tournament_revision ?? point.run.id}-${index}`} cx={point.x} cy={point.y} r={denseChart ? "3" : "5"} tabIndex={0} onMouseEnter={() => setHoveredPoint(index)} onMouseLeave={() => setHoveredPoint(null)} onFocus={() => setHoveredPoint(index)} onBlur={() => setHoveredPoint(null)} />)}
              </svg>
              {hoveredPoint !== null ? <div className={`history-tooltip${tooltipEdge}`} style={{ "--history-tooltip-left": `${(points[hoveredPoint].x / WIDTH) * 100}%`, top: `${(points[hoveredPoint].y / HEIGHT) * 100}%` } as CSSProperties}><strong>{(points[hoveredPoint].probability * 100).toFixed(1)}%</strong><span>{points[hoveredPoint].label}</span></div> : null}
            </div>
            <div className="history-labels"><span>{points[0]?.label}</span><strong>{Math.round(points.at(-1)!.probability * 100)}% now</strong><span>{points.at(-1)?.label}</span></div>
            <div className={denseChart ? "history-snapshots compact" : "history-snapshots"}>{points.map((point, index) => <div key={`${point.run.id}-${index}`}><span>{point.label}</span><strong>{(point.probability * 100).toFixed(1)}%</strong></div>)}</div>
          </>}
        </div>
      </div>
    </section>
  );
}
