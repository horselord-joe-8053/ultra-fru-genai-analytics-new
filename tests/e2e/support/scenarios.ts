/**
 * Canonical chat scenarios (S1–S4) and S5 CRUD fixture — single source for e2e specs and demos.
 */
export type ChatScenarioKind =
  | "sql_aggregate"
  | "sql_geo_state"
  | "sql_geo_city"
  | "semantic_themes";

export type ChatScenario = {
  id: string;
  query: string;
  kind: ChatScenarioKind;
  expectedKeywords: string[];
  expectedRegex?: RegExp;
};

export const ANALYTICS_CHAT_SCENARIOS: readonly ChatScenario[] = [
  {
    id: "S1",
    query: "What's the average rating?",
    kind: "sql_aggregate",
    expectedKeywords: [],
    expectedRegex: /\b[67]\.\d|\b[78](?:\.\d)?\b|\baverage\b.*\b[67]/i,
  },
  {
    id: "S2",
    query: "Which state performed the best in revenue?",
    kind: "sql_geo_state",
    expectedKeywords: ["CA", "California", "california"],
  },
  {
    id: "S3",
    query: "Which city performed the best in revenue?",
    kind: "sql_geo_city",
    expectedKeywords: ["Houston", "Kansas City", "houston", "kansas city"],
  },
  {
    id: "S4",
    query: "What are the top 3 areas that the customers complained about?",
    kind: "semantic_themes",
    expectedKeywords: ["noise", "temperature", "delivery", "installation", "ice", "water", "seal"],
  },
] as const;

export type SuperSaleRecord = {
  id: string;
  customer_id: string;
  brand: string;
  fridge_model: string;
  price: number;
  store_name: string;
  store_address: string;
  feedback_rating: number;
  feedback_sentiment_category: string;
  customer_feedback: string;
  sales_date: string;
};

/** Reserved test row (seed format F###); not in CSV F001–F200. */
export const E2E_SUPER_SALE_RECORD: SuperSaleRecord = {
  id: "F900",
  customer_id: "CUST900",
  brand: "SpaceX",
  fridge_model: "spaceblizzardxx",
  price: 70000,
  store_name: "New York Store",
  store_address: "123 Broadway, New York, NY 10001",
  feedback_rating: 10,
  feedback_sentiment_category: "Positive",
  customer_feedback: "Outstanding purchase — best fridge ever, highly recommend.",
  sales_date: "2026-05-20",
};

export const S5_CRUD_JOURNEY = {
  id: "S5",
  kind: "crud_chat_journey" as const,
  chatQuery: "Which city performed the best in revenue?",
  expectedAnswerKeywords: ["new york"],
  record: E2E_SUPER_SALE_RECORD,
};

export function assertChatAnswer(scenario: ChatScenario, answerText: string): void {
  const text = answerText.trim();
  if (!text) {
    throw new Error(`[${scenario.id}] empty assistant answer`);
  }
  if (scenario.expectedRegex && scenario.expectedRegex.test(text)) {
    return;
  }
  const lower = text.toLowerCase();
  const hits = scenario.expectedKeywords.filter((kw) => lower.includes(kw.toLowerCase()));
  if (hits.length > 0) {
    return;
  }
  if (scenario.expectedRegex) {
    throw new Error(
      `[${scenario.id}] answer did not match regex or keywords. Got: ${text.slice(0, 300)}`,
    );
  }
  throw new Error(
    `[${scenario.id}] answer missing expected keywords ${scenario.expectedKeywords.join(", ")}. Got: ${text.slice(0, 300)}`,
  );
}

export function assertS5ChatAnswer(answerText: string): void {
  const lower = answerText.toLowerCase();
  if (!S5_CRUD_JOURNEY.expectedAnswerKeywords.some((kw) => lower.includes(kw))) {
    throw new Error(`[S5] expected New York in answer. Got: ${answerText.slice(0, 300)}`);
  }
}
