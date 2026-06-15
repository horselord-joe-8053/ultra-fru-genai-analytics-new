import React, { useState, useRef, useEffect, useMemo, useCallback } from "react";
import type { Message } from "../App";
import { getBackendVersion } from "../utils/backendVersion";
import type { BackendVersionInfo } from "../utils/backendVersion";
import ChatHeaderSelect from "./ChatHeaderSelect";

interface CatalogOption {
  id: string;
  display: string;
  enabled: boolean;
}

interface CatalogStack {
  embedding_profile: string;
  chat_choice: string;
  enabled: boolean;
  stack_group?: string | null;
}

interface ModelCatalog {
  embeddings: CatalogOption[];
  chat: CatalogOption[];
  stacks: CatalogStack[];
  allow_override?: boolean;
  cloud_provider?: string;
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

/** Enabled chat logical ids for one embedding lane (catalog-driven, REQ-1). */
export function chatIdsForEmbedding(
  catalog: ModelCatalog,
  embeddingId: string
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const stack of catalog.stacks || []) {
    if (!stack.enabled || stack.embedding_profile !== embeddingId) continue;
    if (!seen.has(stack.chat_choice)) {
      seen.add(stack.chat_choice);
      out.push(stack.chat_choice);
    }
  }
  return out;
}

/** Embedding ids that appear in at least one enabled stack. */
export function embeddingIdsInStacks(catalog: ModelCatalog): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const stack of catalog.stacks || []) {
    if (!stack.enabled) continue;
    if (!seen.has(stack.embedding_profile)) {
      seen.add(stack.embedding_profile);
      out.push(stack.embedding_profile);
    }
  }
  return out;
}

function clampStackSelection(
  catalog: ModelCatalog,
  embed: string,
  chat: string
): { embed: string; chat: string } {
  const defaultEmbed = catalog.defaults.embedding_profile;
  const defaultChat = catalog.defaults.chat_choice;
  let nextEmbed = embed || defaultEmbed;
  const embedIds = embeddingIdsInStacks(catalog);
  if (!embedIds.includes(nextEmbed)) {
    nextEmbed = embedIds[0] || defaultEmbed;
  }
  const allowedChat = chatIdsForEmbedding(catalog, nextEmbed);
  let nextChat = chat || defaultChat;
  if (!allowedChat.includes(nextChat)) {
    nextChat =
      allowedChat.find((id) => catalog.chat.find((c) => c.id === id)?.enabled) ||
      allowedChat[0] ||
      defaultChat;
  }
  return { embed: nextEmbed, chat: nextChat };
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
  const clampedRef = useRef(false);

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
    getBackendVersion(true).then(setVersionInfo).catch(() => {
      getBackendVersion(false).then(setVersionInfo);
    });
  }, []);

  useEffect(() => {
    setCatalogError(null);
    clampedRef.current = false;
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
        if (
          !data?.embeddings?.length ||
          !data?.chat?.length ||
          !data?.stacks?.length
        ) {
          if (data?.embeddings?.length && data?.chat?.length && !data?.stacks?.length) {
            throw new Error(
              "API missing stacks (rebuild/restart fru-api:local after model-catalog update)"
            );
          }
          throw new Error("empty catalog");
        }
        setCatalog(data);
        const { embed, chat } = clampStackSelection(
          data,
          embeddingProfile,
          chatChoice
        );
        if (embed !== embeddingProfile) {
          onEmbeddingProfileChange(embed);
        }
        if (chat !== chatChoice) {
          onChatChoiceChange(chat);
        }
        clampedRef.current = true;
      })
      .catch((err: unknown) => {
        setCatalog(null);
        setCatalogError(err instanceof Error ? err.message : "catalog fetch failed");
      });
  }, []);

  const handleEmbedChange = useCallback(
    (nextEmbed: string) => {
      onEmbeddingProfileChange(nextEmbed);
      if (!catalog) return;
      const allowed = chatIdsForEmbedding(catalog, nextEmbed);
      if (!allowed.includes(chatChoice)) {
        const firstEnabled =
          allowed.find((id) => catalog.chat.find((c) => c.id === id)?.enabled) ||
          allowed[0];
        if (firstEnabled) {
          onChatChoiceChange(firstEnabled);
        }
      }
    },
    [catalog, chatChoice, onEmbeddingProfileChange, onChatChoiceChange]
  );

  const embedOptions = useMemo(() => {
    if (!catalog) return [];
    const inStacks = new Set(embeddingIdsInStacks(catalog));
    return catalog.embeddings
      .filter((e) => inStacks.has(e.id))
      .map((e) => ({ ...e, enabled: e.enabled && inStacks.has(e.id) }));
  }, [catalog]);

  const chatOptions = useMemo(() => {
    if (!catalog || !embeddingProfile) return [];
    const allowed = new Set(chatIdsForEmbedding(catalog, embeddingProfile));
    return catalog.chat
      .filter((c) => allowed.has(c.id))
      .map((c) => ({
        ...c,
        enabled: c.enabled && allowed.has(c.id),
      }));
  }, [catalog, embeddingProfile]);

  const pickersLocked = loading || catalog?.allow_override === false;

  const buildLine = versionInfo ? versionInfo.version : "loading...";
  const scope = versionInfo?.scope ?? null;
  const cloudProvider = versionInfo?.cloud_provider ?? null;
  const region = versionInfo?.region ?? null;
  const cloudDisplay = cloudProvider ? cloudProvider.toUpperCase() : null;
  const scopeDisplay = scope ?? (cloudDisplay ? "unknown" : null);
  const deployLine =
    [cloudDisplay, scopeDisplay, region].filter(Boolean).length > 0
      ? [cloudDisplay && `Provider: ${cloudDisplay}`, scopeDisplay != null && `Scope: ${scopeDisplay}`, region && `Region: ${region}`]
          .filter(Boolean)
          .join(" · ")
      : null;
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

  const showPickers = catalog && catalog.allow_override !== false;

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
            showPickers ? (
              <div className="space-y-0.5 text-[10px] text-gray-500">
                <label className="flex items-center gap-1.5 min-w-0">
                  <span className="text-gray-400 shrink-0 w-[6.75rem]">Embedded Model:</span>
                  <ChatHeaderSelect
                    wide
                    value={embeddingProfile}
                    disabled={pickersLocked}
                    title="Embedding profile for semantic search"
                    options={embedOptions}
                    onChange={handleEmbedChange}
                  />
                </label>
                <label className="flex items-center gap-1.5 min-w-0">
                  <span className="text-gray-400 shrink-0 w-[6.75rem]">Chat Model:</span>
                  <ChatHeaderSelect
                    value={chatChoice}
                    disabled={pickersLocked}
                    title="Chat model for planning and synthesis"
                    options={chatOptions}
                    onChange={onChatChoiceChange}
                  />
                </label>
              </div>
            ) : (
              <div className="text-[10px] text-gray-500 space-y-0.5">
                <p>
                  <span className="text-gray-400">Embedded Model:</span>{" "}
                  {embedOptions.find((e) => e.id === embeddingProfile)?.display ||
                    embeddingProfile}
                </p>
                <p>
                  <span className="text-gray-400">Chat Model:</span>{" "}
                  {chatOptions.find((c) => c.id === chatChoice)?.display || chatChoice}
                </p>
              </div>
            )
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
