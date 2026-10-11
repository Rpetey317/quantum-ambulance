// Publish only explicitly selected runtime assets; never the repository itself.
import { mkdir, readFile, writeFile, cp } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const output = path.join(root, "dist");
await mkdir(output, { recursive: true });
for (const name of ["ui", "main.css", "data/cases", "data/map"]) {
  await cp(path.join(root, name), path.join(output, name), { recursive: true });
}
await cp(path.join(root, "web/main.js"), path.join(output, "main.js"));
const fragment = (await readFile(path.join(root, "index.html"), "utf8"))
  .replace("Qollab Stop or a new Run clears edits.", "Reloading this page clears edits.");
await writeFile(path.join(output, "index.html"), `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Explore ambulance-base placement. Edit a population map and compare greedy, exact and simulated QAOA using actual population coverage.">
<title>Quantum Ambulance · Interactive proof of concept</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%23007d83'/%3E%3Cpath d='M32 16v32M16 32h32' stroke='white' stroke-width='10'/%3E%3C/svg%3E">
<link rel="stylesheet" href="/main.css">
<style>.web-context{max-width:1440px;margin:0 auto;padding:12px 24px;background:#e9f5f4;color:#174f53;font-size:14px}.web-context a{color:inherit;font-weight:600}</style>
</head><body>
<div class="web-context">Interactive proof of concept · QAOA uses a server-side Qiskit simulator (up to 8 candidates, 128 shots). <a href="https://qollab.xyz/u/rpetey317/ambulance-localizer" target="_blank" rel="noopener">Choose a Qollab backend</a> · <a href="https://github.com/Rpetey317/quantum-ambulance" target="_blank" rel="noopener">Code & methodology</a></div>
${fragment}
<script type="module" src="/main.js"></script></body></html>`);
console.log("Built standalone web app in dist/; Qollab entrypoints preserved.");
