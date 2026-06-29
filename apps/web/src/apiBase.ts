export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787";

export type ApiBaseDecisionInput = {
  protocol: string;
  hostname: string;
  port: string;
  search: string;
  envApiUrl?: string;
};

export function isLoopbackHostname(hostname: string): boolean {
  const normalized = hostname.trim().toLowerCase();
  return normalized === "localhost" || normalized === "127.0.0.1" || normalized === "::1" || normalized === "[::1]";
}

export function hasCompanionToken(search: string): boolean {
  return new URLSearchParams(search || "").has("companion_token");
}

export function resolveApiBaseUrl(input: ApiBaseDecisionInput): string {
  const envApiUrl = input.envApiUrl?.trim();
  if (envApiUrl) return envApiUrl;

  if (input.protocol !== "http:" && input.protocol !== "https:") return DEFAULT_API_BASE_URL;

  const hostname = input.hostname.trim();
  const origin = `${input.protocol}//${hostname}${input.port ? `:${input.port}` : ""}`;
  const loopback = isLoopbackHostname(hostname);

  if (!loopback) return origin;
  if (input.port === "8787") return origin;
  if (hasCompanionToken(input.search)) return origin;

  return DEFAULT_API_BASE_URL;
}
