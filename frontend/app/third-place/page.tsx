import { ThirdPlacePageClient } from "@/components/ThirdPlacePageClient";
import { loadCachedThirdPlacePage } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function ThirdPlacePage() {
  try {
    const data = await loadCachedThirdPlacePage();
    return <ThirdPlacePageClient initialForecast={data.forecast} initialStandings={data.standings} />;
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Could not load the third-place race";
    return <ThirdPlacePageClient initialForecast={null} initialStandings={null} initialError={message} />;
  }
}
