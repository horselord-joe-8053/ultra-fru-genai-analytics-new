/**
 * Base URL helpers for Playwright external stacks (Vite preview / dev bind).
 */

/** Resolve ``http://127.0.0.1:{port}`` from env or default. */
export function resolvePlaywrightBaseURL(opts?: {
  portEnv?: string;
  defaultPort?: number;
  host?: string;
}): string {
  const host = opts?.host ?? "127.0.0.1";
  const defaultPort = opts?.defaultPort ?? 4173;
  const envKey = opts?.portEnv ?? "E2E_FRONTEND_PORT";
  const raw = process.env[envKey]?.trim();
  if (raw !== undefined && raw !== "") {
    const p = Number.parseInt(raw, 10);
    if (Number.isFinite(p) && p > 0) {
      return `http://${host}:${p}`;
    }
  }
  return `http://${host}:${defaultPort}`;
}
