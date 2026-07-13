import type { Forecast, Standing, Standings } from "@/lib/types";


function signed(value: number) {
  return value > 0 ? `+${value}` : String(value);
}

export function ThirdPlaceView({ standings, forecast }: { standings: Standings; forecast: Forecast }) {
  const positionByTeam = new Map<number, number>();
  const standingByTeam = new Map<number, Standing>();
  for (const rows of Object.values(standings.groups)) {
    rows.forEach((row, index) => {
      positionByTeam.set(row.team_id, index + 1);
      standingByTeam.set(row.team_id, row);
    });
  }
  const projected = forecast.probabilities
    .filter((row) => row.best_third_probability > 0)
    .sort((a, b) => b.best_third_probability - a.best_third_probability);
  const groupsComplete = Object.values(standings.groups).flat().every((row) => row.played >= 3);

  return <section className="third-page" aria-labelledby="third-page-heading">
    <div className="third-page-intro">
      <div><span className="eyebrow">Round of 32 qualification</span><h1 id="third-page-heading">The third-place race</h1><p>Each group sends its top two teams through. The twelve third-place finishers are then compared with one another, and the best eight also advance.</p></div>
      <div className="rules-card"><strong>How the twelve are ranked</strong><ol><li>Points</li><li>Overall goal difference</li><li>Overall goals scored</li><li>Team conduct score</li><li>FIFA world ranking</li></ol></div>
    </div>

    <div className="third-page-grid">
      <section aria-labelledby="current-third-heading">
        <div className="subsection-heading"><h2 id="current-third-heading">{groupsComplete ? "Final third-place table" : "If the groups ended now"}</h2><p>{groupsComplete ? "The group stage is complete. Green rows are the eight third-place teams that advanced." : "Green rows sit above the eight-team qualification line. Groups are unfinished, so the team occupying third can still change."}</p></div>
        <div className="third-ranking-table"><table><thead><tr><th>#</th><th>Team</th><th>Group</th><th>P</th><th>Pts</th><th>GD</th><th>GF</th><th>Status</th></tr></thead><tbody>
          {standings.best_third.map((row, index) => <tr className={index < 8 ? "qualifying" : "outside"} key={row.team_id}><td>{index + 1}</td><th scope="row">{row.team}</th><td>{row.group}</td><td>{row.played}</td><td>{row.points}</td><td>{signed(row.goal_difference)}</td><td>{row.goals_for}</td><td><span className={index < 8 ? "status-chip in" : "status-chip out"}>{index < 8 ? "In" : "Out"}</span></td></tr>)}
        </tbody></table></div>
      </section>

      <section aria-labelledby="projected-third-heading">
        <div className="subsection-heading"><h2 id="projected-third-heading">{groupsComplete ? "Best-third qualifiers" : "Projected best-third routes"}</h2><p>{groupsComplete ? "These probabilities are resolved from the completed group stage." : "This isolates the chance of advancing specifically in third place—not by winning the group or finishing second."}</p></div>
        <div className="third-projection-list">
          {projected.map((row) => {
            const percent = Math.round(row.best_third_probability * 100);
            const displayPercent = row.best_third_probability < 0.005 ? "<1%" : `${percent}%`;
            const standing = standingByTeam.get(row.team_id);
            return <div className="third-projection-row" key={row.team_id}><div><strong>{row.team}</strong><span>Group {row.group} · {standing?.played ?? 0} played · currently {positionByTeam.get(row.team_id) ?? "–"}{positionByTeam.has(row.team_id) ? ["st", "nd", "rd", "th"][Math.min(positionByTeam.get(row.team_id)!, 4) - 1] : ""}</span></div><div className="third-projection-value"><strong>{displayPercent}</strong><span className="probability-track"><span style={{ width: `${Math.max(percent, 1)}%` }} /></span></div></div>;
          })}
        </div>
      </section>
    </div>
    <p className="third-page-note">The current table uses the public score feed. {groupsComplete ? "Qualification is resolved from completed group results." : "Projections keep completed results fixed, simulate only remaining group matches, and isolate advancement specifically as one of the eight best third-place teams."} Fair-play card totals and official FIFA ranking are not yet in the dataset, so the app uses its pre-tournament rating only as a final deterministic fallback when every available football criterion is still tied.</p>
  </section>;
}
