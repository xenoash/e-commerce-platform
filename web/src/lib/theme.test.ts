import { applyThemeChoice, readThemeChoice, THEME_STORAGE_KEY } from "./theme";

describe("theme choice", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it("defaults to following the system", () => {
    expect(readThemeChoice()).toBe("system");
    localStorage.setItem(THEME_STORAGE_KEY, "sepia");
    expect(readThemeChoice()).toBe("system");
  });

  it("pins light or dark on the root element and remembers it", () => {
    applyThemeChoice("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(readThemeChoice()).toBe("dark");
    applyThemeChoice("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("returns to the system setting by clearing the override", () => {
    applyThemeChoice("dark");
    applyThemeChoice("system");
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
  });
});
