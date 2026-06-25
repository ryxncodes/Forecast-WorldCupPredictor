"use client";

import { useCallback, useState } from "react";
import { ForecastHistory } from "@/components/ForecastHistory";
import { Header } from "@/components/Header";
import { loadForecastHistory } from "@/lib/api";
import type { Forecast } from "@/lib/types";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

type Props = {
  initialRuns: Forecast[];
  initialError?: string | null;
};

export function HistoryPageClient({ initialRuns, initialError = null }: Props) {
  const [runs, setRuns] = useState<Forecast[]>(initialRuns);
  const [error, setError] = useState<string | null>(initialError);

  const refresh = useCallback(async () => {
    try {
      setRuns(await loadForecastHistory());
      setError(null);
    }
    catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load forecast history");
    }
  }, []);

  useAutoRefresh(refresh);

  return <>
    <Header />
    <main id="top">
      {error ? <div className="error-banner" role="alert">{error} <button onClick={refresh}>Try again</button></div> : null}
      {!error && runs.length === 0 ? <div className="loading-state"><span className="spinner spinning" /><p>Loading prediction history…</p></div> : null}
      {runs.length ? <ForecastHistory runs={runs} /> : null}
    </main>
  </>;
}
