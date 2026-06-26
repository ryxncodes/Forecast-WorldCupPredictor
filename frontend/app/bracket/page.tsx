import { BracketPageClient } from "@/components/BracketPageClient";
import { loadCachedBracket } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function BracketPage() {
  try {
    return <BracketPageClient initialBracket={await loadCachedBracket()} />;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Could not load bracket projection";
    return <BracketPageClient initialBracket={null} initialError={message} />;
  }
}
