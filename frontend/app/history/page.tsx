import { HistoryPageClient } from "@/components/HistoryPageClient";
import { loadForecastHistory } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  try {
    return <HistoryPageClient initialRuns={await loadForecastHistory()} />;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Could not load forecast history";
    return <HistoryPageClient initialRuns={[]} initialError={message} />;
  }
}
