import { readFile } from "node:fs/promises";
import { join } from "node:path";

export async function GET() {
  const image = await readFile(join(process.cwd(), "public", "og-worldcup.png"));

  return new Response(new Uint8Array(image), {
    headers: {
      "Cache-Control": "public, max-age=31536000, immutable",
      "Content-Type": "image/png",
    },
  });
}
