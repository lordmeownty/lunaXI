interface W { from_min: number; to_min: number; momentum: number }
export default function MomentumChart({ series, home, away, homeColour, awayColour, focusMin }: { series: W[]; home: string; away: string; homeColour: string; awayColour: string; focusMin?: number | null }) {
  const W = 600, H = 110, mid = H / 2, x = (m: number) => (m / 96) * W;
  const pts = series.map((s) => `${x(s.from_min + 2.5)},${mid - (s.momentum / 100) * (mid - 8)}`).join(" ");
  const first = series[0] ? x(series[0].from_min + 2.5) : 0, last = series.length ? x(series[series.length - 1].from_min + 2.5) : 0;
  return (
    <figure className="pulse" aria-label={`Match pulse: above the line favours ${home}, below favours ${away}`}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="gH" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={homeColour} stopOpacity=".6" /><stop offset="1" stopColor={homeColour} stopOpacity="0" /></linearGradient>
          <linearGradient id="gA" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor={awayColour} stopOpacity=".6" /><stop offset="1" stopColor={awayColour} stopOpacity="0" /></linearGradient>
          <clipPath id="top"><rect x="0" y="0" width={W} height={mid} /></clipPath><clipPath id="bot"><rect x="0" y={mid} width={W} height={mid} /></clipPath>
        </defs>
        <line x1="0" x2={W} y1={mid} y2={mid} className="pulse-axis" />
        <line x1={x(45)} x2={x(45)} y1="4" y2={H - 4} className="pulse-ht" />
        {series.length > 1 && <>
          <polygon points={`${first},${mid} ${pts} ${last},${mid}`} fill="url(#gH)" clipPath="url(#top)" />
          <polygon points={`${first},${mid} ${pts} ${last},${mid}`} fill="url(#gA)" clipPath="url(#bot)" />
          <polyline points={pts} fill="none" stroke="#e6edf6" strokeWidth="1.6" strokeLinejoin="round" />
        </>}
        {focusMin != null && <line x1={x(focusMin)} x2={x(focusMin)} y1="0" y2={H} className="pulse-focus" />}
      </svg>
      <figcaption><span style={{ color: homeColour }}>▲ {home}</span><span>Threat index · 5 min windows</span><span style={{ color: awayColour }}>▼ {away}</span></figcaption>
    </figure>
  );
}
