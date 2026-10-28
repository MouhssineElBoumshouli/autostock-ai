import { ar } from "./ar";
import { en } from "./en";
import { fr } from "./fr";

export type Language = "en" | "fr" | "ar";
export type Messages = typeof en;

const dictionaries: Record<Language, Messages> = { en, fr, ar };

// Each language's name in itself, so anyone can find their own in the menu.
export const languageNames: Record<Language, string> = { fr: "Français", ar: "العربية", en: "English" };
export const languages = Object.keys(languageNames) as Language[];

const STORAGE_KEY = "language";

export function isLanguage(value: unknown): value is Language {
  return typeof value === "string" && value in dictionaries;
}

// The language this device last showed. Before anyone logs in, the browser's own language, else French.
function rememberedLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLanguage(saved)) return saved;
  } catch {
    // Storage can be blocked (private window): fall back below.
  }
  const browser = navigator.language.slice(0, 2);
  return isLanguage(browser) ? browser : "fr";
}

// Chosen once, when the page loads. Changing language reloads the page (see showLanguage), so every
// screen, format and sentence is built in one language and nothing is left half translated.
export const language = rememberedLanguage();
export const t = dictionaries[language];
export const direction: "ltr" | "rtl" = language === "ar" ? "rtl" : "ltr";
// For dates and numbers. Digits stay 0-9 in every language.
export const locale = { en: "en-US", fr: "fr-MA", ar: "ar-MA" }[language] + "-u-nu-latn";

// Shows the app in `next`: remembered on this device, then the page reloads in it.
export function showLanguage(next: Language) {
  if (next === language) return;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    return; // can't remember it, so a reload would come back in the same language
  }
  window.location.reload();
}

// The server writes its error messages in English: this finds the same message in the person's language.
export function translateServerMessage(message: string): string {
  const fixed = t.serverMessages.fixed[message];
  if (fixed) return fixed;
  for (const [pattern, build] of Object.entries(t.serverMessages.patterns)) {
    const match = new RegExp(pattern).exec(message);
    if (match) return build(...match.slice(1));
  }
  return message;
}
