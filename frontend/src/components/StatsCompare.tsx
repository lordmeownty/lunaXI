const ROWS: [string, string, (v: number) => string][] = [["possession_pct", "Possession", (v) => `${Math.round(v)}%`], ["shots", "Shots", String], ["shots_on_target", "On target", String], ["xg", "xG", (v) => v.toFixed(2)], ["final_third_entries", "Final-third entries", String]];
export default function StatsCompare({ stats, home, away }: { stats: any; home: { colour: string; short: string }; away: { colour: string; short: string } }) {
  if (!stats) return null;
  return (
    <div className="stats" role="table" aria-label="Team comparison">
      {ROWS.map(([k, label, fmt]) => {
        const h = stats.home[k] ?? 0, a = stats.away[k] ?? 0, tot = h + a || 1;
        return (
          <div key={k} className="stat-row" role="row">
            <span role="cell" className={h >= a ? "lead" : ""}>{fmt(h)}</span>
            <div className="stat-mid"><small>{label}</small><div className="stat-bar"><i style={{ width: `${(h / tot) * 100}%`, background: home.colour }} /><i style={{ width: `${(a / tot) * 100}%`, background: away.colour }} /></div></div>
            <span role="cell" className={a > h ? "lead" : ""}>{fmt(a)}</span>
          </div>
        );
      })}
    </div>
  );
}
