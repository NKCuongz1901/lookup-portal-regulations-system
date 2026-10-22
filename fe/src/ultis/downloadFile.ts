import type { DocumentDownload } from "@/interface/Document/Document.interface";

export function downloadFile(file: DocumentDownload) {
  const url = new URL(file.url);
  if (url.protocol !== "https:") throw new Error("Invalid download URL");
  // R2 supplies Content-Disposition: attachment. Native navigation avoids CORS
  // requirements and keeps the application's Authorization header off R2 requests.
  const link = document.createElement("a");
  link.href = url.href;
  link.download = file.file_name;
  link.rel = "noreferrer";
  link.referrerPolicy = "no-referrer";
  link.hidden = true;
  document.body.appendChild(link);
  try {
    link.click();
  } finally {
    link.remove();
  }
}
