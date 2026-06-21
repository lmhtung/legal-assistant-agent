export type LegalArticle = {
  id: string;
  article_id: string;
  law_id: string;
  law_name: string;
  doc_type: string;
  database?: string;
  category?: string;
  chapter?: string | null;
  article: string;
  article_title?: string | null;
  content: string;
  author?: string | null;
  extra?: string[];
  score?: number | null;
};

export type LegalAnswerResponse = {
  id?: number | null;
  session_id?: string | null;
  question: string;
  answer: string;
  relevant_docs: string[];
  relevant_articles: string[];
  selected_articles: LegalArticle[];
  debug: Record<string, unknown>;
};

export type ChatResponse = {
  session_id?: string | null;
  message: string;
  answer: LegalAnswerResponse;
  tool_calls: Record<string, unknown>[];
};

export type ChatStreamEvent =
  | { event: "status"; data: { message: string } }
  | { event: "result"; data: ChatResponse }
  | { event: "done"; data: { message: string } }
  | { event: "error"; data: { message: string } };

export type AgentTraceStep = {
  title: string;
  detail: string;
  tone?: "info" | "success" | "warning" | "error";
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  stream: string[];
  trace: AgentTraceStep[];
  sources: string[];
};

export type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
};
