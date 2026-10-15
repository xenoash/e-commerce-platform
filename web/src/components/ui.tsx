import type { ButtonHTMLAttributes, ReactNode } from "react";

import { useI18n } from "../i18n/context";
import { describeProblem } from "../i18n/problems";
import { formatMoney } from "../lib/money";

type MoneyProps = { amount: string | number; currency?: string; className?: string; negative?: boolean };

export function Money({ amount, currency = "SAR", className = "", negative = false }: MoneyProps) {
  return (
    <span dir="ltr" className={`tabular whitespace-nowrap ${className}`}>
      {negative ? "-" : ""}
      {formatMoney(amount, currency)}
    </span>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "danger"; busy?: boolean };

export function Button({ variant = "primary", busy = false, className = "", children, disabled, ...props }: ButtonProps) {
  const styles = {
    primary: "bg-accent text-accent-ink hover:opacity-90",
    quiet: "border border-line bg-surface text-ink hover:border-ink/40",
    danger: "text-bad hover:underline px-0",
  }[variant];
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
      disabled={disabled || busy}
      {...props}
    >
      {busy ? <span className="size-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" /> : null}
      {children}
    </button>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-line bg-surface p-5 ${className}`}>{children}</section>;
}

const TONES = {
  ok: "bg-ok/12 text-ok",
  warn: "bg-warn/12 text-warn",
  bad: "bg-bad/12 text-bad",
  info: "bg-accent/12 text-accent",
  neutral: "bg-ink/8 text-muted",
};

export function Badge({ tone = "neutral", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <span className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function ProblemNotice({ error }: { error: unknown }) {
  const i18n = useI18n();
  if (!error) return null;
  const problem = describeProblem(error, i18n);
  return (
    <div role="alert" className="rounded-lg border border-bad/30 bg-bad/8 px-3 py-2 text-sm text-bad">
      <p className="font-semibold">{problem.message}</p>
      {problem.code ? (
        <p dir="ltr" className="mt-0.5 text-start font-mono text-xs opacity-80">
          {problem.code}
        </p>
      ) : null}
      {problem.fields.length ? (
        <ul className="mt-1 list-disc ps-4 text-xs">
          {problem.fields.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

const STATUS_TONES: Record<string, keyof typeof TONES> = {
  paid: "ok",
  confirmed: "ok",
  succeeded: "ok",
  deferred: "ok",
  reported: "ok",
  cleared: "ok",
  pending_payment: "warn",
  requires_action: "warn",
  pending: "warn",
  issued: "info",
  pending_retry: "warn",
  payment_failed: "bad",
  failed: "bad",
  expired: "bad",
  rejected: "bad",
  needs_attention: "bad",
};

export function StatusBadge({ status, kind }: { status: string; kind: "order" | "payment" | "invoice" }) {
  const { t, has } = useI18n();
  const key = `status.${kind}.${status}`;
  return <Badge tone={STATUS_TONES[status] ?? "neutral"}>{has(key) ? t(key) : status.replaceAll("_", " ")}</Badge>;
}

const PALETTE = ["#7c3aed", "#b45309", "#0f766e", "#be123c", "#1d4ed8", "#4d7c0f", "#a21caf", "#c2410c"];

export function ProductArt({ sku, name, size = "md" }: { sku: string; name: string; size?: "sm" | "md" }) {
  const hash = [...sku].reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) >>> 0, 7);
  const first = PALETTE[hash % PALETTE.length];
  const second = PALETTE[(Math.floor(hash / PALETTE.length) + 3) % PALETTE.length];
  const initials = name
    .split(/\s+/)
    .filter((word) => /^[A-Za-z]/.test(word))
    .slice(0, 2)
    .map((word) => word[0])
    .join("");
  const box = size === "sm" ? "size-12 rounded-lg text-sm" : "aspect-[16/9] w-full rounded-xl text-3xl sm:aspect-[4/3]";
  return (
    <div
      aria-hidden
      className={`grid place-items-center font-bold tracking-tight text-white/90 ${box}`}
      style={{ background: `linear-gradient(135deg, ${first}, ${second})` }}
    >
      {initials}
    </div>
  );
}
