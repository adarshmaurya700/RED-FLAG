import { Suspense } from "react";
import RadarDashboard from "@/components/RadarDashboard";
export default function Page() {
  return (
    <Suspense
      fallback={<div className="loading-panel">Opening the radar…</div>}
    >
      <RadarDashboard />
    </Suspense>
  );
}
