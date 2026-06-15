import React, { useState, useEffect, useRef } from "react";
/**
 * MAIN tab shell: Chat | Execution Log | Batch Analytics.
 * Initial panel widths come from Vite env (build-time); users can drag resize handles.
 * Resized widths are not persisted — only panel visibility is stored in localStorage.
 */
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { Tabs, Tab, Box } from "@mui/material";
import Chat from "./components/Chat";
import BatchAnalyticsPanel from "./components/BatchAnalyticsPanel";
import ExecutionPanel, { ExecutionState } from "./components/ExecutionPanel";
import DataManagement from "./components/DataManagement";
import { handleBackendError } from "./utils/errorHandler";
import {
  stackLabelFromModelContext,
  type StackLabel,
} from "./utils/chatStackLabel";
import type { ModelContextInfo } from "./components/ExecutionPanel";

const theme = createTheme({
  palette: { mode: "light" },
});

export interface Message {
  role: "user" | "assistant";
  text: string;
  /** Display strings from SSE model_context for this request (REQ-4). */
  stackLabel?: StackLabel;
}

export interface QueryResponse {
  question: string;
  mode: string;
  answer: string;
}

const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [executionState, setExecutionState] = useState<ExecutionState>({
    question: null,
    method: null,
    modelContext: null,
    toolCalls: [],
    inProgressStep: null,
    currentIteration: null,
    iterations: null,
    execution_time_ms: null,
    token_usage: null,
    answer: null,
    isStreaming: false,
    error: null,
  });
  const [embeddingProfile, setEmbeddingProfile] = useState<string>(() =>
    localStorage.getItem("embeddingProfile") || ""
  );
  const [chatChoice, setChatChoice] = useState<string>(() =>
    localStorage.getItem("chatChoice") || ""
  );
  const eventSourceRef = useRef<EventSource | null>(null);
  /** Per-stream model_context from SSE — not header dropdown state (REQ-4.5). */
  const streamModelContextRef = useRef<ModelContextInfo | null>(null);

  // Calculate initial panel widths from percentage env vars
  const getInitialPanelWidths = () => {
    const viewportWidth = window.innerWidth;
    
    const execLogPercent = parseFloat(
      import.meta.env.VITE_FRONTEND_EXEC_LOG_PANEL_WIDTH_PERCENT || "0.4"
    );
    const batchAnalyticPercent = parseFloat(
      import.meta.env.VITE_FRONTEND_BATCH_ANALYTIC_PANEL_WIDTH_PERCENT || "0.2"
    );
    
    return {
      executionLog: Math.floor(viewportWidth * execLogPercent),
      batchAnalytics: Math.floor(viewportWidth * batchAnalyticPercent),
    };
  };

  // Panel visibility and width state
  const [panelVisibility, setPanelVisibility] = useState(() => {
    const saved = localStorage.getItem("panelVisibility");
    return saved ? JSON.parse(saved) : { executionLog: true, batchAnalytics: true };
  });
  const [panelWidths, setPanelWidths] = useState(() => getInitialPanelWidths());
  const [isResizing, setIsResizing] = useState<string | null>(null);
  const [resizeStartX, setResizeStartX] = useState(0);
  const [resizeStartWidth, setResizeStartWidth] = useState(0);
  const resizeRef = useRef<{ panel: string; startX: number; startWidth: number } | null>(null);

  // Save panel visibility to localStorage
  useEffect(() => {
    localStorage.setItem("panelVisibility", JSON.stringify(panelVisibility));
  }, [panelVisibility]);

  // Log proxy setup once (browser → frontend port → API port). Always show destination; use /version when VITE_API_PORT unset.
  useEffect(() => {
    const frontendPort = window.location.port || "5173";
    const envApiPort = import.meta.env.VITE_API_PORT || null;
    if (envApiPort) {
      console.info(
        `[FRU] Traffic: browser → localhost:${frontendPort} (frontend) → proxy → localhost:${envApiPort} (API)`
      );
      return;
    }
    fetch("/version", { method: "GET" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        const port = data?.api_port != null ? String(data.api_port) : null;
        const apiPart = port
          ? `localhost:${port} (API)`
          : "API port unknown (backend /version did not return api_port)";
        console.info(
          `[FRU] Traffic: browser → localhost:${frontendPort} (frontend) → proxy → ${apiPart}`
        );
      })
      .catch(() => {
        console.info(
          `[FRU] Traffic: browser → localhost:${frontendPort} (frontend) → proxy → API port unknown (could not reach /version)`
        );
      });
  }, []);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  // Handle panel visibility toggle
  const toggleExecutionLog = () => {
    setPanelVisibility((prev: { executionLog: boolean; batchAnalytics: boolean }) => ({ ...prev, executionLog: !prev.executionLog }));
  };

  const toggleBatchAnalytics = () => {
    setPanelVisibility((prev: { executionLog: boolean; batchAnalytics: boolean }) => ({ ...prev, batchAnalytics: !prev.batchAnalytics }));
  };

  // Resize handlers
  const handleResizeStart = (panel: string, e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(panel);
    setResizeStartX(e.clientX);
    setResizeStartWidth(panelWidths[panel as keyof typeof panelWidths]);
    resizeRef.current = {
      panel,
      startX: e.clientX,
      startWidth: panelWidths[panel as keyof typeof panelWidths],
    };
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !resizeRef.current) return;

      const deltaX = e.clientX - resizeRef.current.startX;
      // The resize handles are positioned BEFORE the panels in the flex layout
      // When dragging RIGHT (positive deltaX), the boundary should move RIGHT
      // This means the panel AFTER the handle should get WIDER
      // Since the handle is BEFORE the panel, dragging right should increase the panel width
      // However, the user reports it moves opposite, so we invert the sign
      const newWidth = resizeRef.current.startWidth - deltaX;
      const minWidth = 200;

      if (newWidth >= minWidth) {
        setPanelWidths((prev: { executionLog: number; batchAnalytics: number }) => ({
          ...prev,
          [resizeRef.current!.panel]: newWidth,
        }));
      }
    };

    const handleMouseUp = () => {
      setIsResizing(null);
      resizeRef.current = null;
    };

    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizing]);

  // Sync loading state with streaming status
  useEffect(() => {
    setLoading(executionState.isStreaming);
  }, [executionState.isStreaming]);

  // Use relative URL - CloudFront will proxy /query requests to ALB
  // In development, Vite proxy handles /query -> localhost:5000
  // In production, CloudFront cache behavior proxies /query -> ALB
  async function sendQuery(text: string) {
    if (!text.trim() || loading) return;
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);

    // Reset execution state
    setExecutionState({
      question: null,
      method: null,
      modelContext: null,
      toolCalls: [],
      inProgressStep: null,
      currentIteration: null,
      iterations: null,
      execution_time_ms: null,
      token_usage: null,
      answer: null,
      isStreaming: true,
      error: null,
    });

    const params = new URLSearchParams({ query: text });
    if (embeddingProfile) params.set("embedding_profile", embeddingProfile);
    if (chatChoice) params.set("chat_choice", chatChoice);

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    streamModelContextRef.current = null;

    const eventSource = new EventSource(`/query/stream?${params.toString()}`);
    eventSourceRef.current = eventSource;

    // Handle SSE events
    eventSource.addEventListener("question", (event) => {
      const data = JSON.parse(event.data);
      setExecutionState((prev) => ({
        ...prev,
        question: data.question,
      }));
    });

    eventSource.addEventListener("method", (event) => {
      const data = JSON.parse(event.data);
      setExecutionState((prev) => ({
        ...prev,
        method: data.method,
      }));
    });

    eventSource.addEventListener("model_context", (event) => {
      const data = JSON.parse(event.data) as ModelContextInfo;
      streamModelContextRef.current = data;
      setExecutionState((prev) => ({
        ...prev,
        modelContext: data,
      }));
    });

    eventSource.addEventListener("iteration_start", (event) => {
      const data = JSON.parse(event.data);
      setExecutionState((prev) => ({
        ...prev,
        currentIteration: data.iteration ?? null,
        inProgressStep: null,
      }));
    });

    eventSource.addEventListener("tool_call_start", (event) => {
      const data = JSON.parse(event.data);
      setExecutionState((prev) => {
        const filtered = prev.toolCalls.filter(
          (tc) => !(tc.status === "running" && tc.tool === data.tool)
        );
        return {
          ...prev,
          inProgressStep: {
            iteration: data.iteration ?? null,
            tool: data.tool,
            input: data.input,
          },
          toolCalls: [
            ...filtered,
            {
              iteration: data.iteration ?? null,
              tool: data.tool,
              input: data.input,
              output: {},
              execution_time_ms: 0,
              status: "running" as const,
            },
          ],
        };
      });
    });

    eventSource.addEventListener("tool_call_complete", (event) => {
      const data = JSON.parse(event.data);
      setExecutionState((prev) => {
        const withoutRunning = prev.toolCalls.filter(
          (tc) => !(tc.status === "running" && tc.tool === data.tool)
        );
        return {
          ...prev,
          inProgressStep: null,
          toolCalls: [
            ...withoutRunning,
            {
              iteration: data.iteration !== null && data.iteration !== undefined ? data.iteration : null,
              tool: data.tool,
              input: data.input,
              output: data.output,
              execution_time_ms: data.execution_time_ms,
              status: "complete" as const,
            },
          ],
        };
      });
    });

    eventSource.addEventListener("synthesis_start", () => {
      setExecutionState((prev) => ({
        ...prev,
        inProgressStep: {
          iteration: null,
          tool: "pseudo_tool#llm_synthesize_answer",
          input: { question: prev.question },
        },
        toolCalls: [
          ...prev.toolCalls.filter(
            (tc) => tc.tool !== "pseudo_tool#llm_synthesize_answer" || tc.status !== "running"
          ),
          {
            iteration: null,
            tool: "pseudo_tool#llm_synthesize_answer",
            input: { question: prev.question },
            output: {},
            execution_time_ms: 0,
            status: "running" as const,
          },
        ],
      }));
    });

    eventSource.addEventListener("complete", (event) => {
      const data = JSON.parse(event.data);
      const answerText = data.answer || "[No answer returned]";
      const stackLabel = stackLabelFromModelContext(streamModelContextRef.current);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: answerText,
          stackLabel,
        },
      ]);
      setExecutionState((prev) => ({
        ...prev,
        iterations: data.iterations,
        execution_time_ms: data.execution_time_ms,
        token_usage: data.token_usage,
        answer: data.answer || null,
        isStreaming: false,
      }));
      eventSource.close();
      eventSourceRef.current = null;
    });

    // Handle error events from server
    eventSource.addEventListener("error", (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const errorMessage = data.message || "Unknown error";
        
        // Handle error with proper logging and truncation
        const { truncated } = handleBackendError(errorMessage, "Server Error Event");
        
        setExecutionState((prev) => ({
          ...prev,
          error: truncated,
          isStreaming: false,
        }));
        
        // Also update Chat panel with user-friendly error
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: `Sorry, an error occurred: ${errorMessage}`,
          },
        ]);
      } catch (e) {
        // JSON parse failed - handle the parsing error
        const { truncated } = handleBackendError(e, "Server Error Event (JSON Parse Failed)");
        
        setExecutionState((prev) => ({
          ...prev,
          error: truncated,
          isStreaming: false,
        }));
        
        // Update Chat panel with generic error
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: "Sorry, something went wrong while processing your query.",
          },
        ]);
      }
      setLoading(false);
      eventSource.close();
      eventSourceRef.current = null;
    });

    // Handle connection errors
    eventSource.onerror = (error) => {
      // Handle error with proper logging and truncation
      const { truncated } = handleBackendError(error, "EventSource Connection");
      
      // Only set error if we haven't received a complete event
      setExecutionState((prev) => {
        if (prev.isStreaming) {
          return {
            ...prev,
            error: truncated,
            isStreaming: false,
          };
        }
        return prev;
      });
      // Update Chat panel with user-friendly error
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Sorry, the connection was interrupted. Please try again.",
        },
      ]);
      
      setLoading(false);
      eventSource.close();
      eventSourceRef.current = null;
    };

    // ❌ REMOVED: Duplicate /query fetch call
    // Chat panel now gets answer from Execution Log's complete event
    // (handled in useEffect that watches executionState.answer)
  }

  const [activeTab, setActiveTab] = useState(0);

  return (
    <ThemeProvider theme={theme}>
      <div className="flex flex-col h-full min-h-0">
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ borderBottom: 1, borderColor: "divider", minHeight: 40, flexShrink: 0 }}>
          <Tab label="Main" />
          <Tab label="Data Management" />
        </Tabs>
        {activeTab === 1 ? (
          <Box sx={{ flex: 1, minHeight: 0, overflow: "auto" }}>
            <DataManagement />
          </Box>
        ) : (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* Chat Panel - Always visible, flexible width */}
      <div className="flex-1 border-r bg-white min-w-0">
        <Chat
          messages={messages}
          onSend={sendQuery}
          loading={loading}
          embeddingProfile={embeddingProfile}
          chatChoice={chatChoice}
          onEmbeddingProfileChange={(v) => {
            setEmbeddingProfile(v);
            localStorage.setItem("embeddingProfile", v);
          }}
          onChatChoiceChange={(v) => {
            setChatChoice(v);
            localStorage.setItem("chatChoice", v);
          }}
        />
      </div>

      {/* Execution Log Panel with Resize Handle */}
      {panelVisibility.executionLog && (
        <>
          {/* Resize Handle - Left side (between Chat and Execution Log) */}
          <div
            className="w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize transition-colors flex-shrink-0 relative group"
            onMouseDown={(e) => handleResizeStart("executionLog", e)}
            style={{ cursor: isResizing === "executionLog" ? "col-resize" : "col-resize" }}
          >
            <div className="absolute inset-y-0 left-0 right-0 group-hover:bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          <div
            className="bg-gray-50 border-l border-r flex flex-col flex-shrink-0 transition-all duration-200 overflow-hidden"
            style={{ width: `${panelWidths.executionLog}px` }}
          >
            <ExecutionPanel
              state={executionState}
              onToggle={toggleExecutionLog}
              isVisible={panelVisibility.executionLog}
            />
          </div>
        </>
      )}

      {/* Batch Analytics Panel with Resize Handle */}
      {panelVisibility.batchAnalytics && (
        <>
          {/* Resize Handle - Between Execution Log and Batch Analytics (only if Execution Log is visible) */}
          {panelVisibility.executionLog && (
            <div
              className="w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize transition-colors flex-shrink-0 relative group"
              onMouseDown={(e) => handleResizeStart("batchAnalytics", e)}
              style={{ cursor: isResizing === "batchAnalytics" ? "col-resize" : "col-resize" }}
            >
              <div className="absolute inset-y-0 left-0 right-0 group-hover:bg-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          )}
          <div
            className="bg-gray-50 flex flex-col border-l flex-shrink-0 transition-all duration-200 overflow-hidden"
            style={{ width: `${panelWidths.batchAnalytics}px` }}
          >
            <div className="flex-1 overflow-hidden">
              <BatchAnalyticsPanel
                onToggle={toggleBatchAnalytics}
                isVisible={panelVisibility.batchAnalytics}
              />
            </div>
          </div>
        </>
      )}

      {/* Show toggle buttons when panels are hidden */}
      {!panelVisibility.executionLog && (
        <div className="flex items-center border-l">
          <button
            onClick={toggleExecutionLog}
            className="px-3 py-4 bg-gray-50 hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
            title="Show Execution Log"
            aria-label="Show Execution Log"
          >
            <span className="text-sm font-medium">◀</span>
          </button>
        </div>
      )}
      {!panelVisibility.batchAnalytics && (
        <div className="flex items-center border-l">
          <button
            onClick={toggleBatchAnalytics}
            className="px-3 py-4 bg-gray-50 hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
            title="Show Batch Analytics"
            aria-label="Show Batch Analytics"
          >
            <span className="text-sm font-medium">◀</span>
          </button>
        </div>
      )}
    </div>
        )}
      </div>
    </ThemeProvider>
  );
};

export default App;
