import { AccuracyPageClient } from "@/components/AccuracyPageClient";
import { finalAccuracy } from "@/lib/final-data";

export default function AccuracyPage() {
  return <AccuracyPageClient initialReport={finalAccuracy} />;
}
