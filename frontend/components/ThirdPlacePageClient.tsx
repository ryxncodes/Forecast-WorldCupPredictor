"use client";

import { Header } from "@/components/Header";
import { ThirdPlaceView } from "@/components/ThirdPlaceView";
import type { Forecast, Standings } from "@/lib/types";

type Props = {
  initialForecast: Forecast | null;
  initialStandings: Standings | null;
  initialError?: string | null;
};

export function ThirdPlacePageClient({ initialForecast, initialStandings, initialError = null }: Props) {
  return <>
    <Header />
    <main id="top">
      {initialError ? <div className="error-banner" role="alert">{initialError}</div> : null}
      {initialForecast && initialStandings ? <ThirdPlaceView forecast={initialForecast} standings={initialStandings} /> : null}
    </main>
  </>;
}
