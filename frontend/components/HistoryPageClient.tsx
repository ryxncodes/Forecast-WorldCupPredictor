"use client";

import { ForecastHistory } from "@/components/ForecastHistory";
import { Header } from "@/components/Header";
import type { Forecast, Match } from "@/lib/types";

type Props = {
  initialRuns: Forecast[];
  initialMatches: Match[];
  initialError?: string | null;
};

export function HistoryPageClient({ initialRuns, initialMatches, initialError = null }: Props) {
  return <>
    <Header />
    <main id="top">
      {initialError ? <div className="error-banner" role="alert">{initialError}</div> : null}
      {initialRuns.length ? <ForecastHistory runs={initialRuns} matches={initialMatches} /> : null}
    </main>
  </>;
}
