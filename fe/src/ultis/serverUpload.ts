import "server-only";
import { DOCUMENT_MAX_FILE_SIZE, documentFileError } from "./documentUpload";

export class UploadValidationError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function readDocumentUpload(request: Request): Promise<FormData> {
  const contentType = request.headers.get("content-type") || "";
  if (!/^multipart\/form-data\s*;/i.test(contentType)) {
    throw new UploadValidationError(415, "Multipart form data required");
  }
  // Bound the whole multipart body, including requests without Content-Length.
  const bodyLimit = DOCUMENT_MAX_FILE_SIZE + 64 * 1024;
  if (Number(request.headers.get("content-length")) > bodyLimit) {
    throw new UploadValidationError(413, "File exceeds the 20MB limit");
  }
  if (!request.body) throw new UploadValidationError(422, "A file is required");
  const reader = request.body.getReader();
  const chunks: ArrayBuffer[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > bodyLimit) {
        await reader.cancel();
        throw new UploadValidationError(413, "File exceeds the 20MB limit");
      }
      chunks.push(Uint8Array.from(value).buffer);
    }
  } finally { reader.releaseLock(); }
  let form: FormData;
  try {
    form = await new Response(new Blob(chunks), { headers: { "Content-Type": contentType } }).formData();
  } catch {
    throw new UploadValidationError(422, "Invalid multipart request");
  }
  const files = form.getAll("file");
  if (files.length !== 1 || !(files[0] instanceof File) || [...form.keys()].some((key) => key !== "file")) {
    throw new UploadValidationError(422, "Exactly one file is required");
  }
  const error = documentFileError(files[0]);
  if (error) throw new UploadValidationError(files[0].size > DOCUMENT_MAX_FILE_SIZE ? 413 : 422, error);
  // The backend verifies the actual PDF/DOCX content, independently of the MIME type.
  return form;
}
