import { BracketPageClient } from "@/components/BracketPageClient";
import { loadBracket } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function BracketPage() {
  try {
    return <BracketPageClient initialBracket={await loadBracket()} />;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Could not load bracket projection";
    return <BracketPageClient initialBracket={null} initialError={message} />;
  }
}
