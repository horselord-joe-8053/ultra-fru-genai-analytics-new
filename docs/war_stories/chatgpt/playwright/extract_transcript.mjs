/**
 * Turn ChatGPT backend share JSON (mapping + linear_conversation) into plain text.
 * Used by fetch_share.mjs and runnable standalone: node extract_transcript.mjs --json-file PATH [-o OUT] [--markdown]
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

function messageBodyText(msg) {
  const content =
    msg.content && typeof msg.content === "object" ? msg.content : {};
  const ctype = content.content_type || "";
  if (ctype === "model_editable_context") {
    const ctx = String(content.model_set_context || "").trim();
    return ctx || null;
  }
  const parts = content.parts;
  if (!parts || !Array.isArray(parts)) return null;
  const meta =
    msg.metadata && typeof msg.metadata === "object" ? msg.metadata : {};
  const attachments = Array.isArray(meta.attachments) ? meta.attachments : [];
  let attI = 0;
  const chunks = [];
  for (const p of parts) {
    if (typeof p === "string") {
      if (p.trim()) chunks.push(p);
    } else if (p && typeof p === "object") {
      if (p.content_type === "image_asset_pointer") {
        let name = null;
        if (
          attI < attachments.length &&
          attachments[attI] &&
          typeof attachments[attI] === "object"
        ) {
          name = attachments[attI].name;
        }
        attI += 1;
        chunks.push(name ? `[image: ${name}]` : "[image]");
      } else {
        const t = p.text;
        if (typeof t === "string" && t.trim()) chunks.push(t.trim());
      }
    }
  }
  if (!chunks.length) return null;
  const out = chunks.join("\n").trim();
  return out || null;
}

function shouldSkipMessage(msg) {
  const meta =
    msg.metadata && typeof msg.metadata === "object" ? msg.metadata : {};
  if (meta.is_visually_hidden_from_conversation) return true;
  const role =
    msg.author && typeof msg.author === "object" ? msg.author.role : undefined;
  return role === "system";
}

function iterMessagesLinear(data) {
  const linear = data.linear_conversation;
  if (!Array.isArray(linear) || linear.length === 0) return null;
  const out = [];
  for (const item of linear) {
    if (!item || typeof item !== "object") continue;
    const m = item.message;
    if (m && typeof m === "object") out.push(m);
  }
  return out;
}

function walkTree(mapping) {
  const out = [];
  const seen = new Set();
  function walk(nodeId) {
    if (seen.has(nodeId)) return;
    seen.add(nodeId);
    const node = mapping[nodeId];
    if (!node || typeof node !== "object") return;
    const msg = node.message;
    if (msg && typeof msg === "object") out.push(msg);
    const children = node.children;
    if (!Array.isArray(children)) return;
    for (const c of children) {
      if (typeof c === "string") walk(c);
    }
  }
  walk("client-created-root");
  return out;
}

function* iterMessages(data) {
  const mapping = data.mapping;
  if (!mapping || typeof mapping !== "object") return;
  let ordered = iterMessagesLinear(data);
  if (ordered == null) ordered = walkTree(mapping);
  for (const msg of ordered) {
    if (!msg || typeof msg !== "object") continue;
    if (shouldSkipMessage(msg)) continue;
    const role =
      (msg.author && typeof msg.author === "object" && msg.author.role) ||
      "unknown";
    const text = messageBodyText(msg);
    if (!text) continue;
    yield [role, text];
  }
}

export function formatTranscriptFromObject(data, markdown = false) {
  const lines = [];
  for (const [role, text] of iterMessages(data)) {
    if (markdown) {
      lines.push(`\n### ${role}\n\n${text}\n`);
    } else {
      lines.push(`\n----- MESSAGE (role=${role}) -----\n${text}\n`);
    }
  }
  const body = lines.join("\n").trim();
  return body ? `${body}\n` : "";
}

/**
 * @param {string} jsonPath
 * @param {string} outPath
 * @param {{ markdown?: boolean }} [options]
 */
export function writeTranscriptFromJsonFile(jsonPath, outPath, options = {}) {
  const markdown = options.markdown ?? false;
  const raw = readFileSync(jsonPath, "utf8");
  const data = JSON.parse(raw);
  if (!Object.prototype.hasOwnProperty.call(data, "mapping")) {
    console.warn("Warning: JSON has no top-level 'mapping' key.");
  }
  const transcript = formatTranscriptFromObject(data, markdown);
  if (!transcript.trim()) {
    throw new Error(
      "No messages extracted (empty mapping or no extractable content).",
    );
  }
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, transcript, "utf8");
}

function parseExtractArgs(argv) {
  const args = argv.slice(2);
  let jsonFile = null;
  let outPath = null;
  let markdown = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--json-file" && args[i + 1]) {
      jsonFile = args[++i];
    } else if ((args[i] === "--out" || args[i] === "-o") && args[i + 1]) {
      outPath = args[++i];
    } else if (args[i] === "--markdown") {
      markdown = true;
    }
  }
  return { jsonFile, outPath, markdown };
}

function runCli() {
  const { jsonFile, outPath, markdown } = parseExtractArgs(process.argv);
  if (!jsonFile) {
    console.error(
      "Usage: node extract_transcript.mjs --json-file PATH [-o OUT] [--markdown]",
    );
    process.exit(1);
  }
  const resolvedJson = resolve(jsonFile);
  try {
    if (outPath) {
      writeTranscriptFromJsonFile(resolvedJson, resolve(outPath), {
        markdown,
      });
    } else {
      const raw = readFileSync(resolvedJson, "utf8");
      const data = JSON.parse(raw);
      const transcript = formatTranscriptFromObject(data, markdown);
      if (!transcript.trim()) {
        console.error(
          "No messages extracted (empty mapping or no extractable content).",
        );
        process.exit(2);
      }
      process.stdout.write(transcript);
    }
  } catch (e) {
    console.error(e.message || e);
    process.exit(2);
  }
}

const __self = fileURLToPath(import.meta.url);
const invokedAsMain =
  process.argv[1] && resolve(process.argv[1]) === resolve(__self);
if (invokedAsMain) {
  runCli();
}
