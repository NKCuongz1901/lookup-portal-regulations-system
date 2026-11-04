import { notFound } from "next/navigation";
import DocumentExtractionReview from "@/Container/ExtractionReview/DocumentExtractionReview";

export const metadata = { title: "Đối chiếu trích xuất" };
export default async function Page({ params }: { params: Promise<{ documentId: string; versionId: string }> }) {
  const { documentId, versionId } = await params;
  if (![documentId, versionId].every((id) => /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id)))) notFound();
  return <DocumentExtractionReview key={versionId} documentId={Number(documentId)} versionId={Number(versionId)} />;
}
