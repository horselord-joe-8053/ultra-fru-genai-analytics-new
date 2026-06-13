import React, { useState, useRef, useEffect } from "react";
import type { Message } from "../App";
import { getBackendVersion } from "../utils/backendVersion";
import type { BackendVersionInfo } from "../utils/backendVersion";

interface ChatProps {
  messages: Message[];
  onSend: (text: string) => void;
  loading: boolean;
}

const Chat: React.FC<ChatProps> = ({ messages, onSend, loading }) => {
  const [input, setInput] = useState("");
  const [versionInfo, setVersionInfo] = useState<BackendVersionInfo | null>(null);
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

  const chatModelLine = versionInfo?.chat_model
    ? `Chat model: ${versionInfo.chat_model}`
    : versionInfo?.chat_model_error
      ? `Chat model: (${versionInfo.chat_model_error})`
      : null;
  const embeddingLine = versionInfo?.embedding_model
    ? `Embedding: ${versionInfo.embedding_profile ?? "default"} → ${versionInfo.embedding_model}`
    : versionInfo?.embedding_model_error
      ? `Embedding: (${versionInfo.embedding_model_error})`
      : versionInfo?.embedding_profile
        ? `Embedding profile: ${versionInfo.embedding_profile}`
        : null;

  const isBundledApiUi =
    versionInfo?.cloud_provider === "local" &&
    versionInfo?.scope === "nonkube" &&
    !import.meta.env.DEV;
  const devFrontendPort =
    versionInfo?.dev_frontend_port ??
    (import.meta.env.DEV && window.location.port ? Number(window.location.port) : null);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
        <div>
          <h1 className="text-lg font-semibold">FRU Analytics Assistant</h1>
          {isBundledApiUi && (
            <p className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-0.5 mt-1 inline-block">
              Bundled UI from API container
              {devFrontendPort != null
                ? ` — for dev, use Vite on port ${devFrontendPort}`
                : " — for dev, use the Vite dev server (see local_deploy_config.yaml)"}
            </p>
          )}
          <div className="text-[10px] text-gray-400 font-mono leading-tight space-y-0.5">
            <p>Build: {buildLine}</p>
            {deployLine && <p>{deployLine}</p>}
            {chatModelLine && <p>{chatModelLine}</p>}
            {embeddingLine && <p>{embeddingLine}</p>}
            {proxyLine && <p>{proxyLine}</p>}
          </div>
          <p className="text-xs text-gray-500">
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
