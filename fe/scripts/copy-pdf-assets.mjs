import { cpSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
const require = createRequire(import.meta.url);
const source = dirname(require.resolve("pdfjs-dist/package.json"));
const target = new URL("../public/pdfjs/", import.meta.url);
mkdirSync(target, { recursive: true });
for (const directory of ["cmaps", "standard_fonts", "wasm"]) {
  cpSync(join(source, directory), new URL(`${directory}/`, target), { recursive: true });
}
