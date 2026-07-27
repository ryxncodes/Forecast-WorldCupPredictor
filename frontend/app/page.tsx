import { HomePageClient } from "@/components/HomePageClient";
import { finalDashboard } from "@/lib/final-data";

export default function Home() {
  return <HomePageClient initialForecast={finalDashboard.forecast} initialStandings={finalDashboard.standings} initialSyncStatus={finalDashboard.sync_status} />;
}
