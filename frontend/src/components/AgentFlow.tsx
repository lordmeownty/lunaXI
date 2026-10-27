/** Visual of the orchestration graph; highlights the path taken by the latest request. */
const POS: Record<string, [number, number]> = { safety: [60, 120], observe: [190, 120], route: [330, 120], lookup: [490, 30], judge: [490, 90],
  summarise: [650, 60], explain: [650, 150], replay: [490, 180], package: [490, 235] };

export default function AgentFlow({ graph, trace }: { graph: any; trace?: any }) {
  if (!graph) return null;
  const agents = new Set<string>((trace?.steps ?? []).map((s: any) => s.agent));
  const hit = (id: string) => {
    const n = graph.nodes.find((x: any) => x.id === id);
    return n && n.agents.split(/ \+ /).some((a: string) => agents.has(a)) || (id === "safety" && agents.has("Safety Guard"));
  };
  return (
    <svg className="flow-svg" viewBox="0 0 760 270" role="img" aria-label="Agent workflow graph">
      <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#5b6b80" /></marker></defs>
      {graph.edges.map((e: any, i: number) => { const [x1, y1] = POS[e.from], [x2, y2] = POS[e.to]; const on = hit(e.from) && hit(e.to);
        return <line key={i} x1={x1 + 52} y1={y1} x2={x2 - 56} y2={y2} stroke={on ? "#479ef5" : "#33404f"} strokeWidth={on ? 2.4 : 1.4} markerEnd="url(#arr)" />; })}
      {graph.nodes.map((n: any) => { const [x, y] = POS[n.id]; const on = hit(n.id);
        return <g key={n.id}><rect x={x - 54} y={y - 20} width="108" height="40" rx="9" fill={on ? "#0f3a63" : "#161b22"} stroke={on ? "#479ef5" : "#2b3542"} />
          <text x={x} y={y - 3} textAnchor="middle" fontSize="11" fontWeight="700" fill="#f3f5f8">{n.id}</text>
          <text x={x} y={y + 11} textAnchor="middle" fontSize="8.5" fill="#9aa6b5">{n.does.slice(0, 24)}</text></g>; })}
    </svg>
  );
}
