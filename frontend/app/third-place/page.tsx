"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { ThirdPlaceView } from "@/components/ThirdPlaceView";
import { loadThirdPlacePage } from "@/lib/api";
import type { Forecast, Standings } from "@/lib/types";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

export default function ThirdPlacePage() {
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [standings, setStandings] = useState<Standings | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await loadThirdPlacePage();
      setForecast(data.forecast);
      setStandings(data.standings);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the third-place race");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useAutoRefresh(refresh);

  return <>
    <Header />
    <main id="top">
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {!error && (!forecast || !standings) ? <div className="loading-state"><span className="spinner spinning" /><p>Loading the third-place race…</p></div> : null}
      {forecast && standings ? <ThirdPlaceView forecast={forecast} standings={standings} /> : null}
    </main>
  </>;
}
