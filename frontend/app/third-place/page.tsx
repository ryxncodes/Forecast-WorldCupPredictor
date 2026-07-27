import { ThirdPlacePageClient } from "@/components/ThirdPlacePageClient";
import { finalDashboard } from "@/lib/final-data";

export default function ThirdPlacePage() {
  return <ThirdPlacePageClient initialForecast={finalDashboard.forecast} initialStandings={finalDashboard.standings} />;
}
