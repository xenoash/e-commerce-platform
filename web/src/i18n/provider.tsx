import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { I18nContext, applyLang, readLang, translator, type Lang } from "./context";

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readLang);

  useEffect(() => applyLang(lang), [lang]);

  const setLang = useCallback((next: Lang) => setLangState(next), []);
  const value = useMemo(() => ({ ...translator(lang), lang, setLang }), [lang, setLang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
