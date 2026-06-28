"use client";

import { useCallback, useState } from "react";
import { Header } from "@/components/Header";
import { MatchList } from "@/components/MatchList";
import { loadMatches } from "@/lib/api";
import type { Match } from "@/lib/types";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

type Props = {
  initialMatches: Match[];
  initialError?: string | null;
};

export function MatchesPageClient({ initialMatches, initialError = null }: Props) {
  const [matches, setMatches] = useState<Match[]>(initialMatches);
  const [error, setError] = useState<string | null>(initialError);

  const refresh = useCallback(async () => {
    try {
      setMatches(await loadMatches());
      setError(null);
    }
    catch (caught) {
      if (!matches.length) {
        setError(caught instanceof Error ? caught.message : "Could not load matches");
      }
    }
  }, [matches.length]);

  useAutoRefresh(refresh, 30_000);

  return <>
    <Header />
    <main id="top">
      {error ? <div className="error-banner" role="alert">{error} <button onClick={refresh}>Try again</button></div> : null}
      {!matches.length && !error ? <div className="loading-state"><span className="spinner spinning" /><p>Loading matches…</p></div> : null}
      {matches.length ? <MatchList matches={matches} /> : null}
    </main>
  </>;
}
