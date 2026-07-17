import { Suspense } from "react";
import ClientDetailPage from "./detail-content";

export function generateStaticParams() {
  return [{ id: "_" }];
}

export default function Page({ params }: { params: { id: string } }) {
  return (
    <Suspense fallback={null}>
      <ClientDetailPage id={params.id} />
    </Suspense>
  );
}
