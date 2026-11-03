import { Suspense } from "react";
import CaseExplorer from "@/components/CaseExplorer";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <Suspense
      fallback={<div className="loading-panel">Opening the case file…</div>}
    >
      <CaseExplorer id={id} />
    </Suspense>
  );
}
