import type { ChatStreamEvent } from "./types";

export function parseSseChunk(raw: string): ChatStreamEvent | null {
  const eventLine = raw.split("\n").find((line) => line.startsWith("event:"));
  const dataLine = raw.split("\n").find((line) => line.startsWith("data:"));
  if (!eventLine || !dataLine) return null;

  const event = eventLine.slice(6).trim() as ChatStreamEvent["event"];
  const data = JSON.parse(dataLine.slice(5).trim() || "{}");
  return { event, data } as ChatStreamEvent;
}
