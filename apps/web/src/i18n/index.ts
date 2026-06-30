import { en } from "./en";
import { zhTW } from "./zh-TW";

export type Locale = "zh-TW" | "en";

export const messages = { "zh-TW": zhTW, en } as const;

export function normalizeLocale(value?: string | null): Locale {
  return value?.toLowerCase().startsWith("en") ? "en" : "zh-TW";
}

export function getMessages(locale?: string | null) {
  return messages[normalizeLocale(locale)];
}
