import React, { useState, useRef, useEffect } from "react";
import type { Message } from "../App";
import { getBackendVersion } from "../utils/backendVersion";
import type { BackendVersionInfo } from "../utils/backendVersion";
import ChatHeaderSelect from "./ChatHeaderSelect";

interface CatalogOption {
  id: string;
  display: string;
  enabled: boolean;
}

interface ModelCatalog {
  embeddings: CatalogOption[];
  chat: CatalogOption[];
  defaults: { embedding_profile: string; chat_choice: string };
}

interface ChatProps {
  messages: Message[];
  onSend: (text: string) => void;
  loading: boolean;
  embeddingProfile: string;
  chatChoice: string;
  onEmbeddingProfileChange: (value: string) => void;
  onChatChoiceChange: (value: string) => void;
}

const Chat: React.FC<ChatProps> = ({
  messages,
  onSend,
  loading,
  embeddingProfile,
  chatChoice,
  onEmbeddingProfileChange,
  onChatChoiceChange,
}) => {
  const [input, setInput] = useState("");
  const [versionInfo, setVersionInfo] = useState<BackendVersionInfo | null>(null);
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input.trim());
    setInput("");
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    // Fetch backend version on component mount
    // Force refresh on mount to ensure we get the latest version after deployments
    getBackendVersion(true).then(setVersionInfo).catch(() => {
      // If force refresh fails, try with cache
      getBackendVersion(false).then(setVersionInfo);
    });
  }, []);

  useEffect(() => {
    setCatalogError(null);
    fetch("/model-catalog")
      .then(async (r) => {
        if (!r.ok) {
          throw new Error(`HTTP ${r.status}`);
        }
        const ct = r.headers.get("content-type") || "";
        if (!ct.includes("application/json")) {
          throw new Error("non-JSON response (check Vite proxy / nginx for /model-catalog)");
        }
        return r.json() as Promise<ModelCatalog>;
      })
      .then((data) => {
        if (!data?.embeddings?.length || !data?.chat?.length) {
          throw new Error("empty catalog");
        }
        setCatalog(data);
        if (!embeddingProfile && data.defaults?.embedding_profile) {
          onEmbeddingProfileChange(data.defaults.embedding_profile);
        }
        if (!chatChoice && data.defaults?.chat_choice) {
          onChatChoiceChange(data.defaults.chat_choice);
        }
      })
      .catch((err: unknown) => {
        setCatalog(null);
        setCatalogError(err instanceof Error ? err.message : "catalog fetch failed");
      });
  }, []);

  const buildLine = versionInfo ? versionInfo.version : "loading...";
  const scope = versionInfo?.scope ?? null;
  const cloudProvider = versionInfo?.cloud_provider ?? null;
  const region = versionInfo?.region ?? null;
  // Explicit Provider and Scope for local and cloud (always show both when we have any deploy info)
  const cloudDisplay = cloudProvider ? cloudProvider.toUpperCase() : null;
  const scopeDisplay = scope ?? (cloudDisplay ? "unknown" : null);
  const deployLine =
    [cloudDisplay, scopeDisplay, region].filter(Boolean).length > 0
      ? [cloudDisplay && `Provider: ${cloudDisplay}`, scopeDisplay != null && `Scope: ${scopeDisplay}`, region && `Region: ${region}`]
          .filter(Boolean)
          .join(" · ")
      : null;
  // Proxy/routing: use backend proxy_info for cloud (GCP kube, etc.); for local, show localhost proxy
  const proxyLine = versionInfo?.proxy_info
    ? versionInfo.proxy_info
    : (() => {
        const apiPort = import.meta.env.VITE_API_PORT || (versionInfo?.api_port != null ? String(versionInfo.api_port) : null);
        return apiPort ? `Proxy: localhost:${window.location.port} → localhost:${apiPort}` : null;
      })();

  const isBundledApiUi =
    versionInfo?.cloud_provider === "local" &&
    versionInfo?.scope === "nonkube" &&
    !import.meta.env.DEV;
  const devFrontendPort =
    versionInfo?.dev_frontend_port ??
    (import.meta.env.DEV && window.location.port ? Number(window.location.port) : null);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2.5 border-b bg-gray-50">
        <h1 className="text-base font-semibold text-gray-900 leading-tight">
          FRU Analytics Assistant
        </h1>

        {isBundledApiUi && (
          <p className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-0.5 mt-1 inline-block">
            Bundled UI from API container
            {devFrontendPort != null
              ? ` — for dev, use Vite on port ${devFrontendPort}`
              : " — for dev, use the Vite dev server (see local_deploy_config.yaml)"}
          </p>
        )}

        <div className="mt-1.5 space-y-1">
          <div className="text-[10px] text-gray-400 font-mono leading-snug space-y-0.5">
            <p>Build: {buildLine}</p>
            {deployLine && <p>{deployLine}</p>}
            {proxyLine && <p>{proxyLine}</p>}
          </div>

          {catalog ? (
            <div className="space-y-0.5 text-[10px] text-gray-500">
              <label className="flex items-center gap-1.5 min-w-0">
                <span className="text-gray-400 shrink-0 w-[6.75rem]">Embedded Model:</span>
                <ChatHeaderSelect
                  wide
                  value={embeddingProfile}
                  disabled={loading}
                  title="Embedding profile for semantic search"
                  options={catalog.embeddings}
                  onChange={onEmbeddingProfileChange}
                />
              </label>
              <label className="flex items-center gap-1.5 min-w-0">
                <span className="text-gray-400 shrink-0 w-[6.75rem]">Chat Model:</span>
                <ChatHeaderSelect
                  value={chatChoice}
                  disabled={loading}
                  title="Chat model for planning and synthesis"
                  options={catalog.chat}
                  onChange={onChatChoiceChange}
                />
              </label>
            </div>
          ) : catalogError ? (
            <p className="text-[10px] text-red-600 leading-snug">
              Models unavailable ({catalogError})
            </p>
          ) : (
            <p className="text-[10px] text-gray-400 leading-snug">Loading models…</p>
          )}

          <p className="text-[10px] text-gray-500 leading-snug pt-0.5">
            Ask about sales, brands, stores, and customer feedback.
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-sm text-gray-500 mt-4">
            Try:{" "}
            <span className="italic">
              "What is the overall average customer rating?"
            </span>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${
              m.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`px-3 py-2 rounded-lg max-w-[70%] text-sm whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-900"
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="text-xs text-gray-400">Thinking…</div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 p-3 border-t bg-gray-50"
      >
        <input
          className="flex-1 border rounded px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          placeholder="Ask a question about FRU sales and feedback…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 text-sm rounded bg-blue-600 text-white disabled:opacity-60"
        >
          Send
        </button>
      </form>
    </div>
  );
};

export default Chat;
