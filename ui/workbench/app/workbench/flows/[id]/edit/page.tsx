import Content from "./detail-content";

export function generateStaticParams() { return [{ id: "_" }]; }

export default function Page({ params }: { params: { id: string } }) {
  return <Content id={params.id} />;
}
