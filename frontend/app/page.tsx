import { HomePageClient } from "@/components/HomePageClient";
import { loadDashboard } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  try {
    const data = await loadDashboard();
    return <HomePageClient initialForecast={data.forecast} initialStandings={data.standings} initialSyncStatus={data.sync_status} />;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Could not load the dashboard";
    return <HomePageClient initialForecast={null} initialStandings={null} initialError={message} />;
  }
}
