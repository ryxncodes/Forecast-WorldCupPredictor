"use client";

import { useMemo, useState } from "react";
import type { Forecast, ProbabilityKey } from "@/lib/types";

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

function pluralizeMatch(count: number) {
  return `${count} ${count === 1 ? "match" : "matches"}`;
}

function milestoneLabel(run: Forecast) {
  if (run.completed_results === 0) return "Pre-tournament";
  if (run.completed_results <= 24) return `After matchday 1 (${run.completed_results}/24 matches)`;
  if (run.completed_results <= 48) return `After matchday 2 (${run.completed_results}/48 matches)`;
  if (run.completed_results < 72) return `Matchday 3 so far (${run.completed_results}/72 matches)`;
  if (run.completed_results === 72) return "After group stage (72 matches)";
  return `After ${run.completed_results} matches`;
}

function groupedMilestones(orderedRuns: Forecast[]): DisplayRun[] {
  const byCompleted = new Map<number, Forecast>();
  for (const run of orderedRuns) byCompleted.set(run.completed_results, run);
  const lastAtOrBefore = (target: number) => [...byCompleted.keys()]
    .filter((completed) => completed <= target)
    .sort((a, b) => b - a)
    .map((completed) => byCompleted.get(completed))
    .find(Boolean);
  const latest = orderedRuns.at(-1);
  const candidates = [
    byCompleted.get(0) ?? orderedRuns[0],
    lastAtOrBefore(24),
    lastAtOrBefore(48),
    latest,
  ].filter(Boolean) as Forecast[];
  const unique = new Map<string | number, DisplayRun>();
  for (const run of candidates) unique.set(run.tournament_revision ?? String(run.id), { run, label: milestoneLabel(run) });
  return [...unique.values()];
}

export function ForecastHistory({ runs }: { runs: Forecast[] }) {
  const latest = runs[0];
  const defaultTeam = latest?.probabilities[0]?.team_id ?? 1;
  const [teamId, setTeamId] = useState(defaultTeam);
  const [metric, setMetric] = useState<Extract<ProbabilityKey, "advance_probability" | "champion_probability">>("advance_probability");
  const [density, setDensity] = useState<"milestones" | "all">("milestones");
  const [hoveredPoint, setHoveredPoint] = useState<number | null>(null);
  const ordered = useMemo(() => [...runs].reverse(), [runs]);
  const displayRuns = useMemo(
    () => density === "milestones"
      ? groupedMilestones(ordered)
      : ordered.map((run) => ({ run, label: run.label })),
    [density, ordered],
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
  const selectedName = latest?.probabilities.find((row) => row.team_id === teamId)?.team ?? "Team";
  const countries = useMemo(
    () => [...(latest?.probabilities ?? [])].sort((a, b) => {
      const eliminatedOrder = Number(a.advance_probability === 0) - Number(b.advance_probability === 0);
      return eliminatedOrder || a.team.localeCompare(b.team);
    }),
    [latest],
  );
  const metricLabel = metric === "advance_probability" ? "advance" : "win the tournament";

  if (!latest) return null;

  return (
    <section id="history" className="history-section" aria-labelledby="history-heading">
      <div className="history-heading">
        <div><h1 id="history-heading">Prediction history</h1><p>Stored group-stage snapshots are shown with the current live knockout projection. The chart defaults to milestones so the trend stays readable; switch to every update for the full replay.</p></div>
      </div>
      <div className="history-workspace">
        <aside className="history-team-panel" aria-label="Choose a country">
          <strong>Countries</strong>
          <div className="history-team-list">{countries.map((row) => {
            const eliminated = row.advance_probability === 0;
            const classes = [row.team_id === teamId ? "selected" : "", eliminated ? "eliminated" : ""].filter(Boolean).join(" ");
            return <button aria-pressed={row.team_id === teamId} className={classes} type="button" key={row.team_id} onClick={() => setTeamId(row.team_id)}><span>{row.team}</span><small>{eliminated ? "Out" : `${Math.round(row[metric] * 100)}%`}</small></button>;
          })}</div>
        </aside>
        <div className="history-detail">
          <div className="history-detail-heading">
            <div><span className="eyebrow">Selected country</span><h2>{selectedName}</h2></div>
            <div className="history-controls">
              <div className="history-metric-toggle" aria-label="Choose chart detail"><button className={density === "milestones" ? "active" : ""} type="button" onClick={() => { setDensity("milestones"); setHoveredPoint(null); }}>Milestones</button><button className={density === "all" ? "active" : ""} type="button" onClick={() => { setDensity("all"); setHoveredPoint(null); }}>Every update</button></div>
              <div className="history-metric-toggle" aria-label="Choose probability"><button className={metric === "advance_probability" ? "active" : ""} type="button" onClick={() => setMetric("advance_probability")}>Advance</button><button className={metric === "champion_probability" ? "active" : ""} type="button" onClick={() => setMetric("champion_probability")}>Champion</button></div>
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
                {points.map((point, index) => <circle aria-label={`${point.label}: ${(point.probability * 100).toFixed(1)}%`} className="history-point" key={point.run.tournament_revision ?? point.run.id} cx={point.x} cy={point.y} r={denseChart ? "3" : "5"} tabIndex={0} onMouseEnter={() => setHoveredPoint(index)} onMouseLeave={() => setHoveredPoint(null)} onFocus={() => setHoveredPoint(index)} onBlur={() => setHoveredPoint(null)} />)}
              </svg>
              {hoveredPoint !== null ? <div className="history-tooltip" style={{ left: `${(points[hoveredPoint].x / WIDTH) * 100}%`, top: `${(points[hoveredPoint].y / HEIGHT) * 100}%` }}><strong>{(points[hoveredPoint].probability * 100).toFixed(1)}%</strong><span>{points[hoveredPoint].label}</span></div> : null}
            </div>
            <div className="history-labels"><span>{points[0]?.label}</span><strong>{Math.round(points.at(-1)!.probability * 100)}% now</strong><span>{points.at(-1)?.label}</span></div>
            <div className={denseChart ? "history-snapshots compact" : "history-snapshots"}>{points.map((point) => <div key={point.run.id}><span>{density === "all" ? pluralizeMatch(point.run.completed_results) : point.label}</span><strong>{(point.probability * 100).toFixed(1)}%</strong></div>)}</div>
          </>}
        </div>
      </div>
    </section>
  );
}
