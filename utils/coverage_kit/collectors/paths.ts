/**
 * Frontend coverage artifact paths (Vitest reports, Playwright raw JSON, landing).
 *
 * Portable — lives under ``utils/coverage_kit/collectors/``. Keep ``DEFAULT_*_REL`` in sync with
 * ``utils/coverage_kit/reporters/cover_layout.py``.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Repository-relative coverage root (config + artifacts). */
export const DEFAULT_COVER_ROOT_REL = "tests/coverage";

/** Default Vitest / Playwright frontend artifact tree under repo root. */
export const DEFAULT_FRONTEND_COVERAGE_REL = `${DEFAULT_COVER_ROOT_REL}/artifacts/frontend`;

const PKG_DIR = path.dirname(fileURLToPath(import.meta.url));

/** Monorepo root when this package lives at ``utils/coverage_kit/collectors/``. */
export function repoRoot(fromImportMetaUrl?: string): string {
  const base = fromImportMetaUrl
    ? path.dirname(fileURLToPath(fromImportMetaUrl))
    : PKG_DIR;
  return path.resolve(base, "../../..");
}

export function frontendCoverageRelFromEnv(): string {
  return (
    process.env.FRONTEND_COVERAGE_DIR?.trim() ||
    process.env.COV_FRONTEND_COVERAGE_DIR?.trim() ||
    DEFAULT_FRONTEND_COVERAGE_REL
  );
}

export function frontendCoverageDir(options?: { repoRoot?: string }): string {
  const rel = frontendCoverageRelFromEnv();
  if (path.isAbsolute(rel)) {
    return rel;
  }
  const root = options?.repoRoot ?? repoRoot();
  return path.resolve(root, rel);
}

/** Vitest ``coverage.exclude`` glob (posix) for the reports tree. */
export function frontendCoverageExcludeGlob(options?: { repoRoot?: string }): string {
  const root = options?.repoRoot ?? repoRoot();
  const rel = path.relative(root, frontendCoverageDir({ repoRoot: root })).split(path.sep).join("/");
  return `${rel}/**`;
}

export function playwrightRawDir(options?: { repoRoot?: string }): string {
  return path.join(frontendCoverageDir(options), "playwright-raw");
}
