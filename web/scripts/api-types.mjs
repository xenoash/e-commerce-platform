import { readFile, writeFile } from "node:fs/promises";

import openapiTS, { astToString } from "openapi-typescript";
import { parse } from "yaml";

const INJECTED_HEADERS = new Set(["X-Store"]);
const source = new URL("../../backend/openapi.yaml", import.meta.url);
const target = new URL("../src/api/schema.d.ts", import.meta.url);

const document = parse(await readFile(source, "utf8"));
for (const operations of Object.values(document.paths)) {
  for (const operation of Object.values(operations)) {
    if (Array.isArray(operation?.parameters)) {
      operation.parameters = operation.parameters.filter(
        (parameter) => !(parameter.in === "header" && INJECTED_HEADERS.has(parameter.name)),
      );
    }
  }
}

await writeFile(target, astToString(await openapiTS(document)));
console.log(`Wrote ${target.pathname}`);
