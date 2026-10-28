// `npm test`: fails if French or Arabic is missing a text, has an empty one, or still shows English.
// Checks the text files (src/i18n), the screens (no English typed straight into a .tsx file) and
// the server's messages (each one has a French and an Arabic version).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { ar } from "../src/i18n/ar.ts";
import { en } from "../src/i18n/en.ts";
import { fr } from "../src/i18n/fr.ts";

const problems: string[] = [];

// Words that are the same in every language: names, file types, units, examples of search words.
const SAME_EVERYWHERE = [
  "AutoStock AI", "Excel", "CSV", "PDF", "OEM", "MAD", "EUR", "USD", "DH", "xlsx", "xls", "csv", "Total", "Stock",
  "Date", "Minimum", "Budget", "Pages", "Filtres", "Famille", "brake pads", "plaquettes de frein", "name@shop.ma",
  "GROQ_API_KEY", "Groq", ".env", "README",
];
// Texts that really are the same in French: "Inactive" (une pièce inactive), "Euro".
const SAME_IN_FRENCH = ["stock.inactive", "settings.currencies.EUR"];
const ENGLISH_WORDS = /(?<!\p{L})(the|and|your|with|from|this|that|is|are|for|of|to|in|no|not|yet|can|will|you)(?!\p{L})/iu;

// A sample value for any argument: works as a string, a number or an object of words.
const sample: unknown = new Proxy(() => "X", {
  get: (_target, key) => (key === Symbol.toPrimitive ? () => "X" : key === "split" ? () => ["X"] : sample),
});

function render(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (typeof value !== "function") return null;
  for (const args of [Array(value.length).fill("X"), Array(value.length).fill(sample)]) {
    try {
      const result = value(...args);
      if (typeof result === "string" && !/undefined|\[object/.test(result)) return result;
    } catch {
      // try the next kind of sample arguments
    }
  }
  return "";
}

function withoutAllowed(text: string): string {
  let rest = text.replace(/\b(X|NaN)\b/g, " ");
  for (const word of SAME_EVERYWHERE) rest = rest.split(word).join(" ");
  return rest;
}

function compare(path: string, english: unknown, translated: unknown, language: "fr" | "ar") {
  if (english !== null && typeof english === "object" && !Array.isArray(english)) {
    if (path === "serverMessages.fixed" || path === "serverMessages.patterns") return; // checked against the server below
    if (translated === null || typeof translated !== "object") {
      problems.push(`${language}: ${path} is missing`);
      return;
    }
    const englishKeys = Object.keys(english as object);
    for (const key of englishKeys) {
      compare(path ? `${path}.${key}` : key, (english as Record<string, unknown>)[key], (translated as Record<string, unknown>)[key], language);
    }
    for (const key of Object.keys(translated as object)) {
      if (!englishKeys.includes(key)) problems.push(`${language}: ${path ? `${path}.` : ""}${key} is not in English (typo?)`);
    }
    return;
  }
  if (Array.isArray(english)) {
    if (!Array.isArray(translated) || translated.length !== english.length) {
      problems.push(`${language}: ${path} should have ${english.length} items`);
      return;
    }
    english.forEach((item, index) => compare(`${path}[${index}]`, item, translated[index], language));
    return;
  }
  const englishText = render(english);
  const text = render(translated);
  if (text === null || text.trim() === "") {
    problems.push(`${language}: ${path} is missing or empty`);
    return;
  }
  const rest = withoutAllowed(text);
  if (text === englishText && rest.trim() !== "" && /[A-Za-z]{3,}/.test(rest) && !SAME_IN_FRENCH.includes(path)) {
    problems.push(`${language}: ${path} is still the English text: "${text}"`);
  } else if (language === "ar" && /[A-Za-z]{2,}/.test(rest)) {
    problems.push(`ar: ${path} has Latin letters: "${text}"`);
  } else if (language === "fr" && ENGLISH_WORDS.test(rest)) {
    problems.push(`fr: ${path} looks English: "${text}"`);
  }
}

compare("", en, fr, "fr");
compare("", en, ar, "ar");

// Every sentence the server can send as an error or an import problem has a French and an Arabic version.
function filesUnder(folder: string): string[] {
  return readdirSync(folder).flatMap((name) => {
    const path = join(folder, name);
    return statSync(path).isDirectory() ? filesUnder(path) : [path];
  });
}

const backendApp = join(import.meta.dirname, "..", "..", "backend", "app");
const serverSentences = new Set<string>();
const constants = new Map<string, string>(); // WRONG_LOGIN -> "Wrong email or password."
const raisedConstants = new Set<string>(); // raise HTTPException(401, WRONG_LOGIN)
for (const file of filesUnder(backendApp).filter((path) => path.endsWith(".py"))) {
  const code = readFileSync(file, "utf8");
  for (const [, name, value] of code.matchAll(/^([A-Z_]+) = "([^"]+)"$/gm)) constants.set(name, value);
  for (const [, name] of code.matchAll(/HTTPException\(\d+, ([A-Z_]+)\)/g)) raisedConstants.add(name);
  const patterns = [
    /HTTPException\(\d+, f?"([^"]+)"/g, // raise HTTPException(404, "This part is not in your shop.")
    /messages\.append\(f?"([^"]+)"\)/g, // import row problems
    /ValueProblem\(f"([^"]+)"\)/g,
    /find_in_shop\([^)]*"([^"]+)"\)/g,
  ];
  for (const pattern of patterns) {
    for (const match of code.matchAll(pattern)) serverSentences.add(match[1]);
  }
}
for (const name of raisedConstants) {
  if (constants.has(name)) serverSentences.add(constants.get(name)!);
}

for (const sentence of serverSentences) {
  // f-string parts like {label} or {remaining} stand for any text or number.
  const examples = ["Quantity", "10"].map((filler) => sentence.replace(/\{[^}]+\}/g, filler));
  for (const [language, words] of [["fr", fr], ["ar", ar]] as const) {
    const known = examples.some(
      (example) =>
        example in words.serverMessages.fixed ||
        Object.keys(words.serverMessages.patterns).some((pattern) => new RegExp(pattern).test(example)),
    );
    if (!known) problems.push(`${language}: no translation for the server message "${sentence}"`);
  }
}

// Screens take every word from src/i18n: no English typed straight into a component.
const screenFiles = filesUnder(join(import.meta.dirname, "..", "src")).filter(
  (path) => path.endsWith(".tsx") && !path.includes(join("pages", "design")),
);
for (const file of screenFiles) {
  const code = readFileSync(file, "utf8").replace(/\/\/.*$/gm, "").replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
  const typed = [
    ...code.matchAll(/>\s*([A-Za-z][A-Za-z ,.'!?]{2,})\s*</g), // <p>Some words</p>
    ...code.matchAll(/(?:aria-label|placeholder|title|alt)="([^"]*[A-Za-z]{3,}[^"]*)"/g),
  ];
  for (const match of typed) problems.push(`${file}: English typed in the screen: "${match[1].trim()}"`);
}

if (problems.length > 0) {
  console.error(problems.join("\n"));
  console.error(`\n${problems.length} text problems.`);
  process.exit(1);
}
console.log(`Text check passed: French and Arabic complete, no English left, ${serverSentences.size} server messages covered.`);
