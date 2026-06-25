"use client";

import { useCallback, useState } from "react";
import { Header } from "@/components/Header";
import { ThirdPlaceView } from "@/components/ThirdPlaceView";
import { loadThirdPlacePage } from "@/lib/api";
import type { Forecast, Standings } from "@/lib/types";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

type Props = {
  initialForecast: Forecast | null;
  initialStandings: Standings | null;
  initialError?: string | null;
};

export function ThirdPlacePageClient({ initialForecast, initialStandings, initialError = null }: Props) {
  const [forecast, setForecast] = useState<Forecast | null>(initialForecast);
  const [standings, setStandings] = useState<Standings | null>(initialStandings);
  const [error, setError] = useState<string | null>(initialError);

  const refresh = useCallback(async () => {
    try {
      const data = await loadThirdPlacePage();
      setForecast(data.forecast);
      setStandings(data.standings);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the third-place race");
    }
  }, []);

  useAutoRefresh(refresh);

  return <>
    <Header />
    <main id="top">
      {error ? <div className="error-banner" role="alert">{error} <button onClick={refresh}>Try again</button></div> : null}
      {!error && (!forecast || !standings) ? <div className="loading-state"><span className="spinner spinning" /><p>Loading the third-place race…</p></div> : null}
      {forecast && standings ? <ThirdPlaceView forecast={forecast} standings={standings} /> : null}
    </main>
  </>;
}
