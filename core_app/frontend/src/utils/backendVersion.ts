/**
 * Backend version utility
 * Fetches backend container image version from the /version endpoint
 */

const VERSION_CACHE_KEY = "backend_version_cache";
const VERSION_CACHE_TTL = 5 * 60 * 1000; // 5 minutes
// Note: To force refresh, clear localStorage: localStorage.removeItem('backend_version_cache')

export interface BackendVersionInfo {
  version: string;
  scope: string | null;
  cloud_provider: string | null;
  region: string | null;
  api_port: number | null;
  proxy_info: string | null;
}

interface VersionCache {
  version: string;
  scope: string | null;
  cloud_provider: string | null;
  region: string | null;
  api_port: number | null;
  proxy_info: string | null;
  timestamp: number;
}

/**
 * Fetches backend version from the /version endpoint
 * Uses caching to avoid repeated API calls
 * @param forceRefresh - If true, bypasses cache and fetches fresh version
 */
export async function getBackendVersion(forceRefresh: boolean = false): Promise<BackendVersionInfo> {
  // Check cache first (unless force refresh is requested)
  if (!forceRefresh) {
    try {
      const cached = localStorage.getItem(VERSION_CACHE_KEY);
      if (cached) {
        const cache: VersionCache = JSON.parse(cached);
        const now = Date.now();
        if (now - cache.timestamp < VERSION_CACHE_TTL) {
          return {
            version: cache.version,
            scope: cache.scope ?? null,
            cloud_provider: cache.cloud_provider ?? null,
            region: cache.region ?? null,
            api_port: cache.api_port ?? null,
            proxy_info: cache.proxy_info ?? null,
          };
        }
      }
    } catch (e) {
      // Ignore cache errors
    }
  }

  try {
    const response = await fetch("/version", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      // Try to get error message from response
      try {
        const errorData = await response.json();
        if (errorData.error) {
        return {
          version: errorData.error,
          scope: null,
          cloud_provider: null,
          region: null,
          api_port: null,
          proxy_info: null,
        };
        }
      } catch (e) {
        // Ignore JSON parse errors
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    // Check for error in response
    if (data.error) {
      return {
        version: data.error,
        scope: null,
        cloud_provider: null,
        region: null,
        api_port: null,
        proxy_info: null,
      };
    }

    const version = data.version;
    const tags = Array.isArray(version) ? version : version ? [version] : [];
    const versionDisplay =
      tags.length > 0 ? `[${tags.join(", ")}]` : "Error: No Version Info Found";

    const apiPort = data.api_port != null && Number.isInteger(Number(data.api_port)) ? Number(data.api_port) : null;
    const proxyInfo = typeof data.proxy_info === "string" ? data.proxy_info : null;
    const result: BackendVersionInfo = {
      version: versionDisplay,
      scope: data.scope ?? null,
      cloud_provider: data.cloud_provider ?? null,
      region: data.region ?? null,
      api_port: apiPort,
      proxy_info: proxyInfo,
    };

    // Cache the result
    try {
      const cache: VersionCache = {
        version: result.version,
        scope: result.scope,
        cloud_provider: result.cloud_provider,
        region: result.region,
        api_port: result.api_port,
        proxy_info: result.proxy_info,
        timestamp: Date.now(),
      };
      localStorage.setItem(VERSION_CACHE_KEY, JSON.stringify(cache));
    } catch (e) {
      // Ignore cache errors
    }

    return result;
  } catch (error) {
    console.warn("Failed to fetch backend version:", error);
    return {
      version: "Error: No Version Info Found",
      scope: null,
      cloud_provider: null,
      region: null,
      api_port: null,
      proxy_info: null,
    };
  }
}
