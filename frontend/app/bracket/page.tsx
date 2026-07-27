import { BracketPageClient } from "@/components/BracketPageClient";
import { finalBracket } from "@/lib/final-data";

export default function BracketPage() {
  return <BracketPageClient initialBracket={finalBracket} />;
}
