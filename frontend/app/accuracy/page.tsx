import { AccuracyPageClient } from "@/components/AccuracyPageClient";
import { loadAccuracy } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AccuracyPage() {
  try {
    return <AccuracyPageClient initialReport={await loadAccuracy()} />;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Could not load model accuracy";
    return <AccuracyPageClient initialReport={null} initialError={message} />;
  }
}
