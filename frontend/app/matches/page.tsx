import { MatchesPageClient } from "@/components/MatchesPageClient";
import { loadMatches } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function MatchesPage() {
  try {
    return <MatchesPageClient initialMatches={await loadMatches()} />;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Could not load matches";
    return <MatchesPageClient initialMatches={[]} initialError={message} />;
  }
}
