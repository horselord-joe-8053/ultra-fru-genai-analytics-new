/**
 * Main tab chat input, messages, and loading state locators.
 */
import { expect, type Locator, type Page } from "@playwright/test";

export function chatInput(page: Page): Locator {
  return page.getByPlaceholder("Ask a question about FRU sales and feedback…");
}

export function sendButton(page: Page): Locator {
  return page.getByRole("button", { name: "Send" });
}

export function assistantBubbles(page: Page): Locator {
  return page.locator(".bg-gray-200.text-gray-900");
}

export function userBubbles(page: Page): Locator {
  return page.locator(".bg-blue-600.text-white");
}

export async function submitChatQuery(page: Page, query: string): Promise<void> {
  const input = chatInput(page);
  await input.fill(query);
  await sendButton(page).click();
}

export async function waitForAssistantReply(page: Page, timeoutMs = 180_000): Promise<string> {
  await expect(page.getByText("Thinking…")).toBeHidden({ timeout: timeoutMs });
  const bubbles = assistantBubbles(page);
  await expect(bubbles.last()).toBeVisible({ timeout: 5_000 });
  const text = (await bubbles.last().innerText()).trim();
  if (!text) {
    throw new Error("Assistant bubble empty");
  }
  return text;
}

export function configStrip(page: Page): Locator {
  return page.getByText(/^Build:/);
}
