// Explicit opt-in for the disposable frontend smoke server only.
import { readFile } from 'node:fs/promises';
if (process.env.EXTRACTION_REVIEW_SMOKE !== '1') throw new Error('R2 mock requires EXTRACTION_REVIEW_SMOKE=1');
const originalFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  if (String(input) === 'https://ui-test.r2.cloudflarestorage.com/tuition.pdf') {
    const pdf = await readFile(new URL('../../../be/.cache/extraction-smoke/tuition-notice.pdf', import.meta.url));
    return new Response(pdf, { headers: { 'Content-Type': 'application/pdf' } });
  }
  return originalFetch(input, init);
};
