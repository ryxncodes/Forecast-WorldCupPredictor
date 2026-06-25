"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { MatchList } from "@/components/MatchList";
import { loadMatches } from "@/lib/api";
import type { Match } from "@/lib/types";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

export default function MatchesPage() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try { setMatches(await loadMatches()); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load matches"); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useAutoRefresh(refresh, 30_000);

  return <>
    <Header />
    <main id="top">
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {!matches.length && !error ? <div className="loading-state"><span className="spinner spinning" /><p>Loading matches…</p></div> : null}
      {matches.length ? <MatchList matches={matches} /> : null}
    </main>
  </>;
}
