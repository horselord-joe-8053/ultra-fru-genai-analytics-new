import { describe, expect, it } from "vitest";

import {
  formatStackLabelLine,
  stackLabelFromModelContext,
} from "./chatStackLabel";

describe("stackLabelFromModelContext", () => {
  it("returns display pair from model_context", () => {
    expect(
      stackLabelFromModelContext({
        embedding_display: "skylark-embedding-vision-251215",
        chat_display: "seed-2-0-pro-260328",
      })
    ).toEqual({
      embeddingDisplay: "skylark-embedding-vision-251215",
      chatDisplay: "seed-2-0-pro-260328",
    });
  });

  it("returns undefined when both displays missing", () => {
    expect(stackLabelFromModelContext(null)).toBeUndefined();
    expect(stackLabelFromModelContext({})).toBeUndefined();
  });
});

describe("formatStackLabelLine", () => {
  it("formats pipe-separated pair in parentheses", () => {
    expect(
      formatStackLabelLine({
        embeddingDisplay: "text-embedding-3-small",
        chatDisplay: "claude-haiku-4-5",
      })
    ).toBe("(text-embedding-3-small | claude-haiku-4-5)");
  });

  it("allows identical answer text with different stack labels", () => {
    const answer = "The average feedback rating is 6.62.";
    const lineA = formatStackLabelLine(
      stackLabelFromModelContext({
        embedding_display: "skylark-embedding-vision-251215",
        chat_display: "deepseek-v4-flash-260425",
      })
    );
    const lineB = formatStackLabelLine(
      stackLabelFromModelContext({
        embedding_display: "skylark-embedding-vision-251215",
        chat_display: "seed-2-0-lite-260228",
      })
    );
    expect(lineA).not.toBe(lineB);
    expect(`${answer}\n${lineA}`).not.toBe(`${answer}\n${lineB}`);
  });
});
