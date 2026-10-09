/**
 * Resolve local deploy ports from config/local/local_deploy_config.yaml.
 * Env overrides: E2E_FRONTEND_PORT, E2E_API_PORT, E2E_DEPLOY_SCOPE (nonkube | kube).
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseYaml } from "yaml";

const e2eRoot = path.dirname(fileURLToPath(import.meta.url));
export const repoRoot = path.resolve(e2eRoot, "../../..");

export type LocalDeployPorts = {
  apiPort: number;
  frontendPort: number;
  scope: "nonkube" | "kube";
};

function readYamlPorts(scope: "nonkube" | "kube"): { api_port?: number; frontend_port?: number } {
  const cfgPath = path.join(repoRoot, "config/local/local_deploy_config.yaml");
  if (!fs.existsSync(cfgPath)) {
    return {};
  }
  const doc = parseYaml(fs.readFileSync(cfgPath, "utf8")) as Record<string, unknown>;
  const section = doc[scope] as Record<string, unknown> | undefined;
  return {
    api_port: typeof section?.api_port === "number" ? section.api_port : undefined,
    frontend_port: typeof section?.frontend_port === "number" ? section.frontend_port : undefined,
  };
}

export function resolveLocalDeployPorts(): LocalDeployPorts {
  const scopeRaw = (process.env.E2E_DEPLOY_SCOPE ?? "nonkube").trim().toLowerCase();
  const scope: "nonkube" | "kube" = scopeRaw === "kube" ? "kube" : "nonkube";
  const yaml = readYamlPorts(scope);

  const frontendEnv = process.env.E2E_FRONTEND_PORT?.trim();
  const apiEnv = process.env.E2E_API_PORT?.trim();

  const frontendPort = frontendEnv
    ? Number.parseInt(frontendEnv, 10)
    : (yaml.frontend_port ?? (scope === "kube" ? 5173 : 5174));

  const apiPort = apiEnv
    ? Number.parseInt(apiEnv, 10)
    : (yaml.api_port ?? (scope === "kube" ? 30080 : 5001));

  return { apiPort, frontendPort, scope };
}

export function frontendBaseUrl(): string {
  const { frontendPort } = resolveLocalDeployPorts();
  // Use localhost (not 127.0.0.1): on macOS Docker often binds IPv6 only; host nginx may own IPv4 :5001.
  return `http://localhost:${frontendPort}`;
}

export function apiBaseUrl(): string {
  const explicit = process.env.INTEGRATION_API_BASE_URL?.trim();
  if (explicit) {
    return explicit.replace(/\/$/, "");
  }
  const { apiPort } = resolveLocalDeployPorts();
  return `http://localhost:${apiPort}`;
}
