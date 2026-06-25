import type { Standings } from "@/lib/types";
import Link from "next/link";

export function StandingsView({ standings }: { standings: Standings }) {
  return (
    <section id="standings" className="standings-section" aria-labelledby="standings-heading">
      <h2 id="standings-heading">Standings by group</h2>
      <div className="bracket-line" aria-hidden="true" />
      <div className="group-grid">
        {Object.entries(standings.groups).map(([group, rows]) => (
          <div className="group-table" key={group}>
            <h3>Group {group}</h3>
            <table><thead><tr><th>#</th><th>Team</th><th>P</th><th>GD</th><th>Pts</th></tr></thead><tbody>
              {rows.map((row, index) => <tr key={row.team_id}><td>{index + 1}</td><th scope="row">{row.team}</th><td>{row.played}</td><td>{row.goal_difference > 0 ? "+" : ""}{row.goal_difference}</td><td>{row.points}</td></tr>)}
            </tbody></table>
          </div>
        ))}
      </div>
      <p className="standings-note"><strong>P:</strong> Played <strong>GD:</strong> Goal difference <strong>Pts:</strong> Points <span>Top 2 plus the eight best third-place teams advance · <Link href="/third-place">Explore the third-place race</Link></span></p>
    </section>
  );
}
