import { MatchesPageClient } from "@/components/MatchesPageClient";
import { finalMatches } from "@/lib/final-data";

export default function MatchesPage() {
  return <MatchesPageClient initialMatches={finalMatches} />;
}
