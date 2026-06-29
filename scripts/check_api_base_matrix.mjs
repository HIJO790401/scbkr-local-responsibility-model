const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787";

function isLoopbackHostname(hostname) {
  const normalized = hostname.trim().toLowerCase();
  return normalized === "localhost" || normalized === "127.0.0.1" || normalized === "::1" || normalized === "[::1]";
}

function hasCompanionToken(search) {
  return new URLSearchParams(search || "").has("companion_token");
}

function resolveApiBaseUrl(input) {
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

const cases = [
  ["CASE 01", { protocol: "http:", hostname: "localhost", port: "5500", search: "", envApiUrl: "http://custom:9999" }, "http://custom:9999"],
  ["CASE 02", { protocol: "file:", hostname: "", port: "", search: "" }, DEFAULT_API_BASE_URL],
  ["CASE 03", { protocol: "http:", hostname: "127.0.0.1", port: "8787", search: "" }, "http://127.0.0.1:8787"],
  ["CASE 04", { protocol: "http:", hostname: "localhost", port: "8787", search: "" }, "http://localhost:8787"],
  ["CASE 05", { protocol: "http:", hostname: "192.168.1.5", port: "8787", search: "" }, "http://192.168.1.5:8787"],
  ["CASE 06", { protocol: "http:", hostname: "192.168.1.5", port: "8788", search: "" }, "http://192.168.1.5:8788"],
  ["CASE 07", { protocol: "http:", hostname: "localhost", port: "5500", search: "" }, DEFAULT_API_BASE_URL],
  ["CASE 08", { protocol: "http:", hostname: "127.0.0.1", port: "5173", search: "" }, DEFAULT_API_BASE_URL],
  ["CASE 09", { protocol: "http:", hostname: "127.0.0.1", port: "8788", search: "?companion_token=abc" }, "http://127.0.0.1:8788"],
  ["CASE 10", { protocol: "http:", hostname: "localhost", port: "8788", search: "" }, DEFAULT_API_BASE_URL],
];

for (const [name, input, expected] of cases) {
  const actual = resolveApiBaseUrl(input);
  if (actual !== expected) {
    throw new Error(`${name} expected ${expected}, got ${actual}`);
  }
}

console.log(`API base matrix passed (${cases.length} cases).`);
