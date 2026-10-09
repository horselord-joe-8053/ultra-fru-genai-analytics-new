/**
 * Stack label helpers for chat assistant bubbles (REQ-4).
 * Labels use catalog/SSE display strings, not logical profile ids.
 */

export interface StackLabel {
  embeddingDisplay: string;
  chatDisplay: string;
}

export interface ModelContextLike {
  embedding_display?: string;
  chat_display?: string;
}

/** Build label from SSE model_context (request-time), not header dropdown state. */
export function stackLabelFromModelContext(
  ctx: ModelContextLike | null | undefined
): StackLabel | undefined {
  const embeddingDisplay = (ctx?.embedding_display ?? "").trim();
  const chatDisplay = (ctx?.chat_display ?? "").trim();
  if (!embeddingDisplay && !chatDisplay) {
    return undefined;
  }
  return { embeddingDisplay, chatDisplay };
}

/** Grey subtitle line under the answer, e.g. "(skylark-… | seed-…)". */
export function formatStackLabelLine(label: StackLabel | undefined): string | null {
  if (!label) {
    return null;
  }
  const { embeddingDisplay, chatDisplay } = label;
  if (!embeddingDisplay && !chatDisplay) {
    return null;
  }
  if (embeddingDisplay && chatDisplay) {
    return `(${embeddingDisplay} | ${chatDisplay})`;
  }
  return `(${embeddingDisplay || chatDisplay})`;
}
