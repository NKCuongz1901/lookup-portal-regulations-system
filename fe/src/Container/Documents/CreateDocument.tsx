"use client";
import type { DocumentDetail } from "@/interface/Document/Document.interface";
import DocumentForm from "./DocumentForm";

export default function CreateDocument({ onClose, onCreated }: {
  onClose: () => void;
  onCreated: (document: DocumentDetail) => void;
}) {
  return <DocumentForm onClose={onClose} onSaved={onCreated} />;
}
