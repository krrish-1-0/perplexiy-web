import { OpenRouter } from "@openrouter/sdk";

export const DOLPHIN_MODEL =
  "cognitivecomputations/dolphin-mistral-24b-venice-edition";

/** Create a client with the visitor's own key (never hardcode it). */
export function getOpenRouterClient(apiKey) {
  const key =
    apiKey || import.meta.env.VITE_OPENROUTER_API_KEY || "";
  if (!key) throw new Error("Missing OpenRouter API key.");
  return new OpenRouter({ apiKey: key });
}

/**
 * Direct OpenRouter call — JS SDK equivalent of the backend's llm_generate().
 * Uses Dolphin Mistral 24B Venice Edition by default; override via `model`.
 */
export async function askDolphin(content, { apiKey, model = DOLPHIN_MODEL } = {}) {
  const openrouter = getOpenRouterClient(apiKey);
  const response = await openrouter.chat.send({
    model,
    messages: [{ role: "user", content }],
  });
  return response.choices[0].message.content;
}

// Example:
// const answer = await askDolphin("What is the meaning of life?", { apiKey });
// console.log(answer);
