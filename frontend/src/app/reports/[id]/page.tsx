import { Suspense } from "react";
import ReferenceExplorer from "@/components/ReferenceExplorer";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <Suspense
      fallback={<div className="loading-panel">Opening the report…</div>}
    >
      <ReferenceExplorer id={id} />
    </Suspense>
  );
}
