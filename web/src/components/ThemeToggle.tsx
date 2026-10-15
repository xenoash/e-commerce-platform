import { useState, type ReactNode } from "react";

import { useI18n } from "../i18n/context";
import { applyThemeChoice, readThemeChoice, type ThemeChoice } from "../lib/theme";

const ICON_PROPS = {
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

const OPTIONS: { choice: ThemeChoice; label: "theme.light" | "theme.system" | "theme.dark"; icon: ReactNode }[] = [
  {
    choice: "light",
    label: "theme.light",
    icon: (
      <svg {...ICON_PROPS}>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
    ),
  },
  {
    choice: "system",
    label: "theme.system",
    icon: (
      <svg {...ICON_PROPS}>
        <rect x="3" y="4" width="18" height="12" rx="2" />
        <path d="M8 20h8M12 16v4" />
      </svg>
    ),
  },
  {
    choice: "dark",
    label: "theme.dark",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
      </svg>
    ),
  },
];

export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>(readThemeChoice);
  const { t } = useI18n();

  function choose(next: ThemeChoice) {
    applyThemeChoice(next);
    setChoice(next);
  }

  return (
    <div role="radiogroup" aria-label={t("theme.label")} className="inline-flex rounded-lg border border-line bg-surface p-0.5">
      {OPTIONS.map((option) => (
        <button
          key={option.choice}
          type="button"
          role="radio"
          aria-checked={choice === option.choice}
          aria-label={t(option.label)}
          title={t(option.label)}
          onClick={() => choose(option.choice)}
          className={`grid size-8 place-items-center rounded-md transition ${
            choice === option.choice ? "bg-accent text-accent-ink" : "text-muted hover:text-ink"
          }`}
        >
          {option.icon}
        </button>
      ))}
    </div>
  );
}
