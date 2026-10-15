import { useI18n, type Lang } from "../i18n/context";

const LANGUAGES: { lang: Lang; label: string }[] = [
  { lang: "en", label: "EN" },
  { lang: "ar", label: "ع" },
];

export function LanguageToggle() {
  const { lang, setLang, t } = useI18n();
  return (
    <div role="radiogroup" aria-label={t("language.label")} className="inline-flex rounded-lg border border-line bg-surface p-0.5">
      {LANGUAGES.map((option) => (
        <button
          key={option.lang}
          type="button"
          role="radio"
          lang={option.lang}
          aria-checked={lang === option.lang}
          aria-label={option.lang === "en" ? "English" : "العربية"}
          onClick={() => setLang(option.lang)}
          className={`grid h-8 min-w-8 place-items-center rounded-md px-2 text-sm font-semibold transition ${
            lang === option.lang ? "bg-accent text-accent-ink" : "text-muted hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
