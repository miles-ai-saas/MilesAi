import { Suspense } from "react";
import Content from "./detail-content";

export function generateStaticParams() { return [{ id: "_" }]; }

export default function Page({ params }: { params: { id: string } }) {
  return (
    <Suspense fallback={null}>
      <Content id={params.id} />
    </Suspense>
  );
}
