export type LegalArticle = {
  id: string;
  article_id: string;
  law_id: string;
  law_name: string;
  doc_type: string;
  database: string;
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

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  stream: string[];
  sources: string[];
};
