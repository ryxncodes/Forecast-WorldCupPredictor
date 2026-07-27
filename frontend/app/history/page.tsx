import { HistoryPageClient } from "@/components/HistoryPageClient";
import { finalHistory, finalMatches } from "@/lib/final-data";

export default function HistoryPage() {
  return <HistoryPageClient initialRuns={finalHistory} initialMatches={finalMatches} />;
}
