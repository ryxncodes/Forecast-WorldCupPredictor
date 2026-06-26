"use client";

import { useCallback, useState } from "react";
import { ForecastTable } from "@/components/ForecastTable";
import { Header } from "@/components/Header";
import { StandingsView } from "@/components/StandingsView";
import { loadDashboard } from "@/lib/api";
import { useAutoRefresh } from "@/lib/useAutoRefresh";
import type { Forecast, Standings, SyncStatus } from "@/lib/types";

type Props = {
  initialForecast: Forecast | null;
  initialStandings: Standings | null;
  initialSyncStatus?: SyncStatus | null;
  initialError?: string | null;
};

export function HomePageClient({ initialForecast, initialStandings, initialSyncStatus = null, initialError = null }: Props) {
  const [forecast, setForecast] = useState<Forecast | null>(initialForecast);
  const [standings, setStandings] = useState<Standings | null>(initialStandings);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(initialSyncStatus);
  const [error, setError] = useState<string | null>(initialError);

  const refresh = useCallback(async () => {
    try {
      const data = await loadDashboard();
      setForecast(data.forecast);
      setStandings(data.standings);
      setSyncStatus(data.sync_status);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the dashboard");
    }
  }, []);

  useAutoRefresh(refresh);

  return (
    <>
      <Header simulations={forecast?.simulations ?? 10_000} />
      <main id="top">
        {error ? <div className="error-banner" role="alert"><strong>Something went wrong.</strong> {error} <button onClick={refresh}>Try again</button></div> : null}
        {!forecast || !standings ? <div className="loading-state"><span className="spinner spinning" /><p>Loading the tournament…</p></div> : null}
        {forecast && standings ? <>
          <ForecastTable forecast={forecast} syncStatus={syncStatus} />
          <div className="lower-dashboard"><StandingsView standings={standings} /></div>
        </> : null}
      </main>
    </>
  );
}
