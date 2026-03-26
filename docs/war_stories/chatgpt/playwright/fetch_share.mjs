#!/usr/bin/env node
/**
 * Fetch ChatGPT share JSON using headless Chromium (Playwright).
 * Accepts a public share URL in either form:
 *   https://chatgpt.com/share/<uuid>
 *   https://chatgpt.com/backend-api/share/<uuid>
 * Always navigates to the backend-api URL (the pretty /share/ page is HTML, not JSON).
 *
 * Usage:
 *   node fetch_share.mjs <url> [--out path.json]
 *
 * Default outputs (under this package):
 *   test_result/raw_json/result_YYMMDD_hhmmss.json
 *   test_result/transcripts/result_YYMMDD_hhmmss.txt  (via extract_transcript.mjs)
 */

import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { writeTranscriptFromJsonFile } from "./extract_transcript.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));

const DEFAULT_INPUT =
  "https://chatgpt.com/backend-api/share/69c46fa8-6ae4-83a1-ab69-301e4ee04b36";

const UUID_RE =
  /([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i;

function log(step, total, message, detail) {
  const prefix = `[fetch_share ${step}/${total}]`;
  if (detail !== undefined) {
    console.log(`${prefix} ${message}`, detail);
  } else {
    console.log(`${prefix} ${message}`);
  }
}

function parseArgs(argv) {
  const args = argv.slice(2);
  let outPath = null;
  const positional = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--out" && args[i + 1]) {
      outPath = args[++i];
    } else if (!args[i].startsWith("-")) {
      positional.push(args[i]);
    }
  }
  return {
    input: (positional[0] || DEFAULT_INPUT).trim(),
    outPath,
  };
}

/**
 * @returns {{ shareId: string, fetchUrl: string, inputKind: 'pretty' | 'backend' | 'bare-uuid' }}
 */
function normalizeShareInput(raw) {
  const trimmed = raw.trim();
  const m = trimmed.match(UUID_RE);
  if (!m) {
    throw new Error(
      `No ChatGPT share UUID found. Expected a URL like https://chatgpt.com/share/<uuid> or .../backend-api/share/<uuid>. Got: ${trimmed.slice(0, 120)}`,
    );
  }
  const shareId = m[1];
  const lower = trimmed.toLowerCase();
  let inputKind = "bare-uuid";
  if (lower.includes("/backend-api/share/")) {
    inputKind = "backend";
  } else if (lower.includes("chatgpt.com/share/") || /\/share\//i.test(trimmed)) {
    inputKind = "pretty";
  }
  const fetchUrl = `https://chatgpt.com/backend-api/share/${shareId}`;
  return { shareId, fetchUrl, inputKind };
}

function resultStampFilename() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  const yy = String(d.getFullYear()).slice(-2);
  const yymmdd = `${yy}${p(d.getMonth() + 1)}${p(d.getDate())}`;
  const hhmmss = `${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
  return `result_${yymmdd}_${hhmmss}.json`;
}

function defaultArtifactPaths() {
  const name = resultStampFilename();
  const rawDir = join(__dirname, "test_result", "raw_json");
  const transcriptDir = join(__dirname, "test_result", "transcripts");
  mkdirSync(rawDir, { recursive: true });
  mkdirSync(transcriptDir, { recursive: true });
  const jsonPath = join(rawDir, name);
  const stem = name.replace(/\.json$/i, "");
  const transcriptPath = join(transcriptDir, `${stem}.txt`);
  return { jsonPath, transcriptPath };
}

/**
 * Resolve JSON output path and matching transcript under test_result/transcripts/.
 */
function resolveOutputPaths(outPath) {
  if (!outPath) {
    return defaultArtifactPaths();
  }
  const jsonPath = resolve(outPath);
  const stem = basename(jsonPath).replace(/\.json$/i, "") || "result";
  const transcriptDir = join(__dirname, "test_result", "transcripts");
  mkdirSync(dirname(jsonPath), { recursive: true });
  mkdirSync(transcriptDir, { recursive: true });
  const transcriptPath = join(transcriptDir, `${stem}.txt`);
  return { jsonPath, transcriptPath };
}

function looksLikeCloudflareChallenge(html) {
  return (
    html.includes("cdn-cgi/challenge-platform") ||
    html.includes("_cf_chl_opt") ||
    html.includes("challenge-error-text") ||
    /__cf_chl/i.test(html)
  );
}

async function main() {
  const TOTAL_STEPS = 10;

  log(1, TOTAL_STEPS, "Parse CLI arguments");
  const { input, outPath } = parseArgs(process.argv);
  log(1, TOTAL_STEPS, "  input URL / string:", input);

  log(2, TOTAL_STEPS, "Normalize to backend-api fetch URL");
  const { shareId, fetchUrl, inputKind } = normalizeShareInput(input);
  log(2, TOTAL_STEPS, "  detected share UUID:", shareId);
  log(2, TOTAL_STEPS, "  input form:", inputKind);
  log(2, TOTAL_STEPS, "  will GET (JSON API):", fetchUrl);

  log(3, TOTAL_STEPS, "Launch headless Chromium");
  const browser = await chromium.launch({
    headless: true,
    args: [
      "--disable-blink-features=AutomationControlled",
      "--no-sandbox",
      "--disable-dev-shm-usage",
    ],
  });
  log(3, TOTAL_STEPS, "  browser started");

  log(4, TOTAL_STEPS, "Create browser context and page (browser-like headers)");
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    locale: "en-GB",
    viewport: { width: 1280, height: 720 },
    extraHTTPHeaders: {
      Accept: "application/json,text/plain,*/*",
      "Accept-Language": "en-GB,en;q=0.9",
      "Sec-Ch-Ua":
        '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
      "Sec-Ch-Ua-Mobile": "?0",
      "Sec-Ch-Ua-Platform": '"macOS"',
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
      "Sec-Fetch-User": "?1",
      "Upgrade-Insecure-Requests": "1",
    },
  });
  const page = await context.newPage();
  log(4, TOTAL_STEPS, "  page ready");

  log(5, TOTAL_STEPS, "Navigate to backend share URL (wait: domcontentloaded)");
  let response;
  try {
    response = await page.goto(fetchUrl, {
      waitUntil: "domcontentloaded",
      timeout: 90_000,
    });
  } catch (e) {
    await browser.close();
    console.error(`[fetch_share] Navigation failed: ${e.message}`);
    process.exit(1);
  }
  log(5, TOTAL_STEPS, "  navigation finished");

  const status = response?.status() ?? 0;
  const contentType = response?.headers()?.["content-type"] ?? "";
  log(6, TOTAL_STEPS, "Inspect response", { httpStatus: status, contentType });

  const likelyJson = contentType.includes("application/json");
  if (!likelyJson) {
    log(6, TOTAL_STEPS, "  waiting 3s for possible challenge / redirect settle");
    await new Promise((r) => setTimeout(r, 3000));
  }

  const body = await response.text();
  log(6, TOTAL_STEPS, "  body length (chars):", body.length);

  log(7, TOTAL_STEPS, "Close browser");
  await browser.close();
  log(7, TOTAL_STEPS, "  closed");

  const trimmed = body.trimStart();

  log(8, TOTAL_STEPS, "Validate body and parse JSON");
  if (trimmed.startsWith("<") || looksLikeCloudflareChallenge(body)) {
    console.error(
      `[fetch_share] Got HTML (likely Cloudflare challenge), not JSON. HTTP ${status} content-type=${contentType}`,
    );
    console.error("First 400 chars:\n", body.slice(0, 400));
    process.exit(2);
  }

  if (!trimmed.startsWith("{")) {
    console.error("[fetch_share] Unexpected body (not a JSON object). First 400 chars:\n", body.slice(0, 400));
    process.exit(3);
  }

  let data;
  try {
    data = JSON.parse(body);
  } catch (e) {
    console.error("[fetch_share] JSON parse error:", e.message);
    process.exit(4);
  }

  const mapping = data.mapping;
  const nNodes = mapping && typeof mapping === "object" ? Object.keys(mapping).length : 0;
  log(8, TOTAL_STEPS, "  OK — title:", data.title ?? "");
  log(8, TOTAL_STEPS, "  mapping node count:", nNodes);

  log(9, TOTAL_STEPS, "Write raw JSON");
  const { jsonPath, transcriptPath } = resolveOutputPaths(outPath);
  mkdirSync(dirname(jsonPath), { recursive: true });
  writeFileSync(jsonPath, JSON.stringify(data, null, 2), "utf8");
  log(9, TOTAL_STEPS, "  path:", jsonPath);

  log(10, TOTAL_STEPS, "Generate transcript (extract_transcript.mjs)");
  try {
    writeTranscriptFromJsonFile(jsonPath, transcriptPath);
    log(10, TOTAL_STEPS, "  path:", transcriptPath);
  } catch (e) {
    console.error("[fetch_share] Transcript step failed:", e.message);
    process.exit(5);
  }

  process.exit(0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
