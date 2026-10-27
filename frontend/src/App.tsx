import { useEffect, useState } from "react";
import Brand from "./components/Brand";
import Home from "./pages/Home";
import SignIn from "./pages/SignIn";
import Workspace from "./pages/Workspace";
import { AuthProvider, useAuth } from "./lib/auth";
import type { Surface } from "./lib/types";

/** Routes: #/ (home) · #/match/<id> · #/match/<id>/<recaps|studio|approvals|operations> */
function parse(): { matchId: string | null; surface: Surface } {
  const m = location.hash.match(/^#\/match\/([^/]+)(?:\/(\w+))?/);
  return { matchId: m ? decodeURIComponent(m[1]) : null, surface: (m?.[2] as Surface) || "match" };
}
export const navigate = (matchId: string | null, surface: Surface = "match") => {
  location.hash = matchId ? `#/match/${matchId}${surface !== "match" ? `/${surface}` : ""}` : "";
};

function Routes() {
  const { me, ready } = useAuth();
  const [route, setRoute] = useState(parse());
  useEffect(() => { const on = () => setRoute(parse()); window.addEventListener("hashchange", on); return () => window.removeEventListener("hashchange", on); }, []);
  if (!ready) return <main className="loading-screen"><Brand /><div className="spinner" /></main>;
  if (!me) return <SignIn />;
  return route.matchId
    ? <Workspace key={route.matchId} matchId={route.matchId} surface={route.surface} go={navigate} />
    : <Home open={(id) => navigate(id)} />;
}

export default function App() { return <AuthProvider><Routes /></AuthProvider>; }
