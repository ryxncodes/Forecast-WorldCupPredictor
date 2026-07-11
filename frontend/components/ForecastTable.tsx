"use client";

import { useEffect, useMemo, useState } from "react";
import type { Forecast, ProbabilityKey, SyncStatus } from "@/lib/types";
import { SortIcon } from "./Icons";

const columns: { key: ProbabilityKey; label: string; optional?: boolean }[] = [
  { key: "advance_probability", label: "Advance / R32" },
  { key: "win_group_probability", label: "Win group" },
  { key: "runner_up_probability", label: "Runner-up", optional: true },
  { key: "best_third_probability", label: "Best third" },
  { key: "round_of_16_probability", label: "Round of 16" },
  { key: "quarterfinal_probability", label: "Quarterfinal" },
  { key: "semifinal_probability", label: "Semifinal", optional: true },
  { key: "final_probability", label: "Final", optional: true },
  { key: "champion_probability", label: "Champion" },
];

const alwaysVisibleColumns = new Set<ProbabilityKey>(["champion_probability"]);
const eliminatedStageOrder: Record<string, number> = {
  "Group stage": 0,
  "Round of 32": 1,
  "Round of 16": 2,
  Quarterfinal: 3,
  Semifinal: 4,
  Final: 5,
};

function formatProbability(value: number, eliminated: boolean) {
  const percent = value * 100;
  if (eliminated) return "0%";
  if (percent === 0) return "<0.01%";
  if (percent < 1) return `${percent.toFixed(2)}%`;
  if (percent < 10) return `${percent.toFixed(1)}%`;
  return `${Math.round(percent)}%`;
}

function ProbabilityCell({ value, eliminated }: { value: number; eliminated: boolean }) {
  const percent = value * 100;
  const width = Math.max(0, Math.min(100, percent));
  return <div className="probability-cell" title={`${percent.toFixed(2)}%`}><span>{formatProbability(value, eliminated)}</span><span className="probability-track"><span style={{ width: `${width}%` }} /></span></div>;
}

function resolvedProbability(value: number) {
  return value === 0 || value === 1;
}

function eliminatedClass(stage: string | null | undefined) {
  if (!stage) return "";
  return ` eliminated-${stage.toLowerCase().replaceAll(" ", "-")}`;
}

function parseApiDate(value: string) {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
}

function formatDataDateTime(value: string | null, mode: "utc" | "local") {
  if (!value) return "No completed matches";
  const parts = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: mode === "utc" ? "UTC" : undefined,
    timeZoneName: "short",
  }).formatToParts(parseApiDate(value));
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("month")} ${part("day")}, ${part("year")} at ${part("hour")}:${part("minute")} ${part("dayPeriod")} ${part("timeZoneName")}`;
}

function LocalUpdateTime({ value }: { value: string | null }) {
  const [useLocalTime, setUseLocalTime] = useState(false);
  useEffect(() => setUseLocalTime(true), []);
  return <time dateTime={value ?? undefined}>{formatDataDateTime(value, useLocalTime ? "local" : "utc")}</time>;
}

export function ForecastTable({ forecast, syncStatus }: { forecast: Forecast; syncStatus?: SyncStatus | null }) {
  const rows = forecast.probabilities;
  const [sortKey, setSortKey] = useState<ProbabilityKey>("champion_probability");
  const hiddenColumns = useMemo(() => new Set(forecast.hidden_probability_keys ?? []), [forecast.hidden_probability_keys]);
  const visibleColumns = useMemo(
    () => columns.filter((column) => (
      !hiddenColumns.has(column.key)
      && (alwaysVisibleColumns.has(column.key)
      || rows.some((row) => !resolvedProbability(row[column.key]))
      )
    )),
    [hiddenColumns, rows],
  );
  useEffect(() => {
    if (!visibleColumns.some((column) => column.key === sortKey)) {
      setSortKey("champion_probability");
    }
  }, [sortKey, visibleColumns]);
  const sortedRows = useMemo(
    () => [...rows].sort((a, b) => {
      const eliminatedOrder = Number(Boolean(a.eliminated_stage)) - Number(Boolean(b.eliminated_stage));
      if (eliminatedOrder) return eliminatedOrder;
      if (a.eliminated_stage && b.eliminated_stage) {
        const stageOrder = (eliminatedStageOrder[a.eliminated_stage] ?? 99)
          - (eliminatedStageOrder[b.eliminated_stage] ?? 99);
        return stageOrder || a.team.localeCompare(b.team);
      }
      return b[sortKey] - a[sortKey];
    }),
    [rows, sortKey],
  );

  return (
    <section id="forecast" className="forecast-section" aria-labelledby="forecast-heading">
      <div className="section-heading">
        <div><h1 id="forecast-heading">World Cup 2026 forecast</h1><p>An adaptive machine learning predictor updates team strength from completed results, projects goal probabilities for the remaining games, and simulates the tournament bracket thousands of times.</p></div>
        <div className="data-status"><strong>Forecast updated <LocalUpdateTime value={forecast.created_at} /></strong><span>{forecast.completed_results}/104 matches complete</span>{syncStatus?.checked_at ? <small>Scores checked <LocalUpdateTime value={syncStatus.checked_at} /></small> : null}</div>
      </div>
      <div className="table-scroll">
        <table className="forecast-table">
          <thead><tr><th className="rank-column">#</th><th>Team</th><th>Group</th>{visibleColumns.map((column) => <th className={column.optional ? "optional-column" : ""} key={column.key}><button className={sortKey === column.key ? "sort-button selected" : "sort-button"} type="button" onClick={() => setSortKey(column.key)}>{column.label}<SortIcon /></button></th>)}</tr></thead>
          <tbody>{sortedRows.map((row, index) => {
            const eliminated = Boolean(row.eliminated_stage);
            return <tr className={eliminated ? `eliminated${eliminatedClass(row.eliminated_stage)}` : ""} key={row.team_id}><td className="rank-column">{index + 1}</td><th scope="row">{row.team}{eliminated ? <span className="eliminated-badge">{row.eliminated_stage}</span> : null}</th><td className="group-cell">{row.group}</td>{visibleColumns.map((column) => <td className={column.optional ? "optional-column" : ""} key={column.key}><ProbabilityCell value={row[column.key]} eliminated={eliminated} /></td>)}</tr>;
          })}</tbody>
        </table>
      </div>
      <div className="table-note"><span>Probabilities are estimated from repeated simulated tournaments. Resolved stage columns are hidden once every team is either through or eliminated from that stage.</span><span>Active teams are sorted by {columns.find((column) => column.key === sortKey)?.label} probability. Eliminated teams are grouped by exit round.</span></div>
    </section>
  );
}
