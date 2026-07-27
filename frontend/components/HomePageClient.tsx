"use client";

import { ForecastTable } from "@/components/ForecastTable";
import { Header } from "@/components/Header";
import { StandingsView } from "@/components/StandingsView";
import type { Forecast, Standings, SyncStatus } from "@/lib/types";

type Props = {
  initialForecast: Forecast | null;
  initialStandings: Standings | null;
  initialSyncStatus?: SyncStatus | null;
  initialError?: string | null;
};

export function HomePageClient({ initialForecast, initialStandings, initialSyncStatus = null, initialError = null }: Props) {
  return (
    <>
      <Header />
      <main id="top">
        {initialError ? <div className="error-banner" role="alert"><strong>Something went wrong.</strong> {initialError}</div> : null}
        {initialForecast && initialStandings ? <>
          <ForecastTable forecast={initialForecast} syncStatus={initialSyncStatus} />
          <div className="lower-dashboard"><StandingsView standings={initialStandings} /></div>
        </> : null}
      </main>
    </>
  );
}
