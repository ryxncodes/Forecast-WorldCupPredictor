import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const manifestPath = resolve(process.cwd(), ".next/prerender-manifest.json");
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
const expectedRoutes = ["/", "/accuracy", "/bracket", "/history", "/matches", "/third-place"];
const missing = expectedRoutes.filter((route) => !manifest.routes[route]);

if (missing.length) {
  console.error(`Archived routes are not prerendered: ${missing.join(", ")}`);
  process.exit(1);
}

const accuracy = JSON.parse(await readFile(resolve(process.cwd(), "data/final/accuracy.json"), "utf8"));
if (accuracy.matches.length !== 72 || accuracy.knockout_predictions.matches.length !== 32) {
  console.error(`Archived Accuracy is incomplete: ${accuracy.matches.length} group, ${accuracy.knockout_predictions.matches.length} knockout`);
  process.exit(1);
}
const labeledRows = [...accuracy.matches, ...accuracy.knockout_predictions.matches]
  .filter((match) => "prediction_source" in match);
if (labeledRows.length) {
  console.error("Public Accuracy rows still contain provenance labels");
  process.exit(1);
}

console.log(`Prerendered archived routes: ${expectedRoutes.join(", ")}`);
console.log(`Complete prediction history: ${accuracy.matches.length} group, ${accuracy.knockout_predictions.matches.length} knockout`);
