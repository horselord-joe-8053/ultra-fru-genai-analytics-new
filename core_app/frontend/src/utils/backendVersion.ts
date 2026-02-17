/**
 * Backend version utility
 * Fetches backend container image version from the /version endpoint
 */

const VERSION_CACHE_KEY = "backend_version_cache";
const VERSION_CACHE_TTL = 5 * 60 * 1000; // 5 minutes
// Note: To force refresh, clear localStorage: localStorage.removeItem('backend_version_cache')

interface VersionCache {
  version: string;
  timestamp: number;
}

/**
 * Fetches backend version from the /version endpoint
 * Uses caching to avoid repeated API calls
 * @param forceRefresh - If true, bypasses cache and fetches fresh version
 */
export async function getBackendVersion(forceRefresh: boolean = false): Promise<string> {
  // Check cache first (unless force refresh is requested)
  if (!forceRefresh) {
    try {
      const cached = localStorage.getItem(VERSION_CACHE_KEY);
      if (cached) {
        const cache: VersionCache = JSON.parse(cached);
        const now = Date.now();
        if (now - cache.timestamp < VERSION_CACHE_TTL) {
          return cache.version;
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
          return errorData.error;
        }
      } catch (e) {
        // Ignore JSON parse errors
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    // Check for error in response
    if (data.error) {
      return data.error;
    }

    const version = data.version;
    if (!version) {
      return "Error: No Version Info Found";
    }

    // version is [tag1, tag2, ...]; format as "[tag1, tag2, ...]" for display
    const tags = Array.isArray(version) ? version : [version];
    const display = tags.length > 0 ? `[${tags.join(", ")}]` : "Error: No Version Info Found";

    // Cache the result
    try {
      const cache: VersionCache = {
        version: display,
        timestamp: Date.now(),
      };
      localStorage.setItem(VERSION_CACHE_KEY, JSON.stringify(cache));
    } catch (e) {
      // Ignore cache errors
    }

    return display;
  } catch (error) {
    console.warn("Failed to fetch backend version:", error);
    return "Error: No Version Info Found";
  }
}
