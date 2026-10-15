import { ApiProblem } from "../api/client";

export function newIdempotencyKey() {
  return `chk_${crypto.randomUUID()}`;
}

export function keepKeyAfter(error: unknown) {
  if (!(error instanceof ApiProblem)) return true;
  if (error.code === "REQUEST_IN_PROGRESS") return true;
  return error.status >= 500;
}
