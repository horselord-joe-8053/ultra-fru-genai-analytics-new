/**
 * Shared chat scenario runner for e2e tests and live demos.
 * E2e uses strict: true (default) — keyword + execution-log asserts.
 * Demo tour passes strict: false — submit, wait, log; no answer keyword checks.
 */
import { test, type Page, type TestInfo } from "@playwright/test";
import type { ChatScenario } from "../../support/scenarios";
import { assertChatAnswer } from "../../support/scenarios";
import { demoPause, logE2eStep } from "../../helpers/core/step-log";
import { submitChatQuery, waitForAssistantReply } from "../../helpers/ui/chat";
import { assertNoExecutionError, waitForExecutionCompleted } from "../../helpers/ui/execution-panel";
import { isAgentLikelyDisabled } from "../../helpers/core/stack";

export type RunChatScenarioOptions = {
  mode?: "test" | "demo";
  /** When false, skip answer keywords and execution-log error asserts (demo narration). Default true. */
  strict?: boolean;
  skipAgentCheck?: boolean;
  assertAnswer?: (scenario: ChatScenario, answerText: string) => void;
};

export async function runChatScenario(
  page: Page,
  scenario: ChatScenario,
  options: RunChatScenarioOptions = {},
  testInfo?: TestInfo,
): Promise<string> {
  const mode = options.mode ?? "test";
  const strict = options.strict ?? true;
  const scope = mode === "demo" ? "demo" : "test";

  logE2eStep(scope, scenario.id, `Ask: ${scenario.query}`, testInfo);
  if (mode === "demo") {
    await demoPause();
  }

  if (!options.skipAgentCheck && mode === "test") {
    const disabled = await isAgentLikelyDisabled(page.request);
    if (disabled) {
      test.skip(true, "Agent-based query processing is disabled");
    }
  }

  await submitChatQuery(page, scenario.query);
  const answer = await waitForAssistantReply(page);
  await waitForExecutionCompleted(page);

  if (strict) {
    await assertNoExecutionError(page);
    const assertFn = options.assertAnswer ?? assertChatAnswer;
    assertFn(scenario, answer);
  }

  logE2eStep(scope, scenario.id, `Answer OK (${answer.slice(0, 80)}…)`, testInfo);
  if (mode === "demo") {
    await demoPause();
  }
  return answer;
}
