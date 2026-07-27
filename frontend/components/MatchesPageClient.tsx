"use client";

import { Header } from "@/components/Header";
import { MatchList } from "@/components/MatchList";
import type { Match } from "@/lib/types";

type Props = {
  initialMatches: Match[];
  initialError?: string | null;
};

export function MatchesPageClient({ initialMatches, initialError = null }: Props) {
  return <>
    <Header />
    <main id="top">
      {initialError ? <div className="error-banner" role="alert">{initialError}</div> : null}
      {initialMatches.length ? <MatchList matches={initialMatches} /> : null}
    </main>
  </>;
}
