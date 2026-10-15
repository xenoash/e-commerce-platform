import { ApiProblem } from "../api/client";
import { moneyText } from "../lib/money";
import type { I18n } from "./context";

type Translate = Pick<I18n, "t" | "has">;

const MONEY_FIELDS = ["remaining", "required", "current", "current_total", "expected_total", "available", "credit_limit", "outstanding"];

export function problemVars(data: Record<string, unknown> = {}) {
  const vars: Record<string, string | number> = {};
  for (const [name, value] of Object.entries(data)) {
    if (typeof value === "number") vars[name] = value;
    else if (typeof value === "string") vars[name] = MONEY_FIELDS.includes(name) ? moneyText(value) : value;
    else if (Array.isArray(value) && value.every((item) => typeof item === "string")) vars[name] = value.join(", ");
  }
  return vars;
}

export function codeMessage(i18n: Translate, code: string, data?: Record<string, unknown>, fallback?: string) {
  const key = `problem.${code}`;
  return i18n.has(key) ? i18n.t(key, problemVars(data)) : (fallback ?? code);
}

export type DescribedProblem = { message: string; code?: string; fields: string[] };

export function describeProblem(error: unknown, i18n: Translate): DescribedProblem {
  if (!(error instanceof ApiProblem)) {
    return { message: i18n.t("problem.NETWORK"), fields: [] };
  }
  const body = error.body;
  const reason = typeof body.reason === "string" && i18n.has(`problem.${body.reason}`) ? body.reason : undefined;
  const message = codeMessage(i18n, reason ?? body.code, body, body.detail);
  const fields = (body.errors ?? []).map((item) => {
    const field = item.field?.split(".").pop() ?? "";
    const labelKey = `field.${field}`;
    const label = i18n.has(labelKey) ? i18n.t(labelKey) : field;
    const errorKey = `fieldError.${item.code}`;
    return i18n.has(errorKey) ? i18n.t(errorKey, { field: label }) : `${label}: ${item.message}`;
  });
  return { message, code: body.code, fields };
}
