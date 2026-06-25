"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Activity, MessageSquarePlus, PanelLeft, Search, Send, SquarePen, Trash2 } from "lucide-react";
import { parseSseChunk } from "@/lib/sse";
import type { AgentTraceStep, ChatMessage, ChatResponse, ChatStreamEvent, Conversation, LegalAnswerResponse } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const DEFAULT_DATABASE = process.env.NEXT_PUBLIC_DEFAULT_DATABASE || "default";
const LEGACY_STORAGE_KEYS = ["mscai_conversations", "mscai_active_conversation_id", "mscai_session_id"];

function createId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createConversation(): Conversation {
  const id = createId();
  const now = Date.now();
  return { id, title: "Đoạn chat mới", messages: [], createdAt: now, updatedAt: now };
}

function compactTitle(text: string) {
  const value = text.replace(/\s+/g, " ").trim();
  return value.length > 44 ? `${value.slice(0, 44)}...` : value || "Đoạn chat mới";
}


function describeValue(value: unknown) {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "không có";
  if (typeof value === "boolean") return value ? "bật" : "tắt";
  if (value === null || value === undefined || value === "") return "không có";
  return String(value);
}

function readToolCalls(answer: LegalAnswerResponse) {
  const value = answer.debug?.tool_calls;
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

function buildTrace(response: ChatResponse, liveStream: string[]): AgentTraceStep[] {
  const answer = response.answer;
  const debug = answer.debug || {};
  const toolCalls = readToolCalls(answer);
  const searchCall = toolCalls.find((item) => item.name === "search_legal_articles");
  const intentCall = toolCalls.find((item) => item.name === "analyze_intent");
  const prepareCall = toolCalls.find((item) => item.name === "prepare_retrieval_query");
  const categoryCall = toolCalls.find((item) => item.name === "classify_categories");
  const legalFlag = describeValue(debug.legal_flag || intentCall?.result);
  const mode = describeValue(debug.retrieval_mode);
  const categories = describeValue(debug.categories);
  const searchArgs = typeof searchCall?.args === "object" && searchCall?.args ? (searchCall.args as Record<string, unknown>) : {};
  const topK = describeValue(searchArgs.top_k);
  const numResults = describeValue(searchCall?.num_results ?? answer.selected_articles?.length ?? 0);

  const trace: AgentTraceStep[] = [
    {
      title: "Nhận câu hỏi",
      detail: `Session ${response.session_id || "hiện tại"}; câu hỏi dài ${response.message.length} ký tự.`,
      tone: "info",
    },
    {
      title: "Đọc short-memory",
      detail: `Memory ${describeValue(debug.memory_enabled)}; dùng thread theo session để giữ ngữ cảnh đoạn chat đang mở.`,
      tone: "info",
    },
    {
      title: "Phân tích ý định",
      detail: legalFlag === "SKIP" ? "SKIP: câu hỏi không cần truy hồi pháp luật." : "NEXT: câu hỏi được xử lý bằng legal RAG.",
      tone: legalFlag === "SKIP" ? "warning" : "success",
    },
  ];

  if (legalFlag !== "SKIP") {
    trace.push({
      title: "Chuẩn bị truy vấn retrieval",
      detail: `Mode ${mode}; retrieval query: ${describeValue(debug.retrieval_question)}.`,
      tone: "info",
    });
    if (debug.rewritten_question) {
      trace.push({ title: "Rewrite query", detail: describeValue(debug.rewritten_question), tone: "success" });
    }
    if (debug.hypothetical_answer) {
      trace.push({ title: "HyDE", detail: describeValue(debug.hypothetical_answer), tone: "success" });
    }
    trace.push({
      title: "Phân loại category",
      detail: categoryCall ? `LLM chọn: ${categories}.` : `Dùng category cấu hình/request: ${categories}.`,
      tone: "info",
    });
    trace.push({
      title: "Hybrid search",
      detail: `Tool backend search_legal_articles; top_k ${topK}; kết quả ${numResults}; per_category ${describeValue(debug.per_category)}.`,
      tone: Number(searchCall?.num_results ?? 0) > 0 ? "success" : "warning",
    });
  }

  trace.push({
    title: "Tổng hợp câu trả lời",
    detail: `Nguồn điều luật: ${answer.relevant_articles?.length || 0}; văn bản: ${answer.relevant_docs?.length || 0}.`,
    tone: answer.relevant_articles?.length ? "success" : "warning",
  });

  if (liveStream.length) {
    trace.push({ title: "SSE backend", detail: liveStream.join(" → "), tone: "info" });
  }

  return trace;
}

export default function Home() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [input, setInput] = useState("");
  const [showStream, setShowStream] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeId) || conversations[0],
    [activeId, conversations],
  );
  const messages = activeConversation?.messages || [];

  useEffect(() => {
    for (const key of LEGACY_STORAGE_KEYS) {
      window.localStorage.removeItem(key);
    }
    const initial = [createConversation()];
    setConversations(initial);
    setActiveId(initial[0].id);
  }, []);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    requestAnimationFrame(() => {
      element.scrollTo({ top: element.scrollHeight, behavior: isSending ? "auto" : "smooth" });
    });
  }, [messages, isSending, showStream]);

  const visibleConversations = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase();
    const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);
    if (!keyword) return sorted;
    return sorted.filter((item) => {
      const haystack = [item.title, ...item.messages.map((message) => message.content)].join(" ").toLowerCase();
      return haystack.includes(keyword);
    });
  }, [conversations, searchTerm]);

  function patchConversation(id: string, updater: (conversation: Conversation) => Conversation) {
    setConversations((items) => items.map((item) => (item.id === id ? updater(item) : item)));
  }

  function newChat() {
    const next = createConversation();
    setConversations((items) => [next, ...items]);
    setActiveId(next.id);
    setSearchTerm("");
    setInput("");
  }

  function deleteChat(conversationId: string) {
    setConversations((items) => {
      const remaining = items.filter((item) => item.id !== conversationId);
      if (remaining.length === 0) {
        const next = createConversation();
        setActiveId(next.id);
        return [next];
      }
      if (conversationId === activeId) {
        setActiveId(remaining[0].id);
      }
      return remaining;
    });
  }

  function updateAssistant(conversationId: string, assistantId: string, updater: (message: ChatMessage) => ChatMessage) {
    patchConversation(conversationId, (conversation) => ({
      ...conversation,
      updatedAt: Date.now(),
      messages: conversation.messages.map((item) => (item.id === assistantId ? updater(item) : item)),
    }));
  }

  function handleStreamEvent(event: ChatStreamEvent, conversationId: string, assistantId: string) {
    if (event.event === "status") {
      updateAssistant(conversationId, assistantId, (message) => ({ ...message, stream: [...message.stream, event.data.message] }));
      return;
    }
    if (event.event === "error") {
      updateAssistant(conversationId, assistantId, (message) => ({
        ...message,
        content: event.data.message || "Có lỗi khi gọi backend.",
        stream: [...message.stream, "Lỗi"],
        trace: [...message.trace, { title: "Lỗi", detail: event.data.message || "Backend trả lỗi.", tone: "error" }],
      }));
      return;
    }
    if (event.event === "result") {
      const answer = event.data.answer;
      updateAssistant(conversationId, assistantId, (message) => ({
        ...message,
        content: answer.answer || "Không có câu trả lời.",
        sources: answer.relevant_articles || [],
        stream: [...message.stream, "Đã nhận kết quả"],
        trace: buildTrace(event.data, [...message.stream, "Đã nhận kết quả"]),
      }));
      return;
    }
    if (event.event === "done") {
      updateAssistant(conversationId, assistantId, (message) => ({ ...message, stream: [...message.stream, event.data.message] }));
    }
  }

  async function submitChat(question: string) {
    if (!question.trim() || isSending) return;
    const conversationId = activeConversation?.id || createConversation().id;
    const text = question.trim();
    const userMessage: ChatMessage = { id: createId(), role: "user", content: text, stream: [], trace: [], sources: [] };
    const assistantId = createId();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "Đang tạo câu trả lời...",
      stream: [],
      trace: [{ title: "Khởi tạo", detail: "Đã gửi câu hỏi tới backend legal chat stream.", tone: "info" }],
      sources: [],
    };

    patchConversation(conversationId, (conversation) => ({
      ...conversation,
      title: conversation.messages.length ? conversation.title : compactTitle(text),
      messages: [...conversation.messages, userMessage, assistantMessage],
      updatedAt: Date.now(),
    }));
    setActiveId(conversationId);
    setInput("");
    setIsSending(true);

    try {
      const response = await fetch(`${API_BASE}/api/v1/legal/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: conversationId,
          message: text,
          databases: [DEFAULT_DATABASE],
          top_k: 8,
        }),
      });
      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";
        for (const chunk of chunks) {
          const event = parseSseChunk(chunk);
          if (event) handleStreamEvent(event, conversationId, assistantId);
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không gọi được backend.";
      updateAssistant(conversationId, assistantId, (item) => ({
        ...item,
        content: message,
        stream: [...item.stream, "Lỗi kết nối"],
        trace: [...item.trace, { title: "Lỗi kết nối", detail: message, tone: "error" }],
      }));
    } finally {
      setIsSending(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitChat(input);
  }

  return (
    <main className={sidebarOpen ? "shell" : "shell sidebarClosed"}>
      {sidebarOpen ? (
        <aside className="sidebar">
          <div className="brand">
            <span>MscAI</span>
            <button className="iconButton" onClick={() => setSidebarOpen(false)} aria-label="Ẩn sidebar"><PanelLeft size={19} /></button>
          </div>
          <nav className="nav">
            <button className="navItem active" onClick={newChat}><MessageSquarePlus size={20} /> Đoạn chat mới</button>
            <button className="navItem" onClick={() => setSearchOpen((value) => !value)}><Search size={20} /> Tìm kiếm đoạn chat</button>
          </nav>
          {searchOpen ? (
            <input
              className="searchInput"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              autoFocus
              placeholder="Nhập từ khóa"
            />
          ) : null}
          <div className="sectionTitle">Đoạn chat</div>
          <div className="chatList">
            {visibleConversations.length === 0 ? <span className="muted">Không có đoạn chat</span> : null}
            {visibleConversations.map((conversation) => {
              const selected = conversation.id === activeConversation?.id;
              return (
                <div className={selected ? "chatRow selected" : "chatRow"} key={conversation.id}>
                  <button className="chatLink" onClick={() => setActiveId(conversation.id)}>
                    <span>{conversation.title}</span>
                    <small>{conversation.messages.length ? `${Math.ceil(conversation.messages.length / 2)} lượt hỏi` : "Mới"}</small>
                  </button>
                  <button
                    className="deleteChat"
                    type="button"
                    disabled={isSending && selected}
                    onClick={() => deleteChat(conversation.id)}
                    aria-label={`Xóa ${conversation.title}`}
                    title="Xóa đoạn chat"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              );
            })}
          </div>
        </aside>
      ) : null}

      <section className="chatArea">
        <header className="topbar">
          {!sidebarOpen ? <button className="iconButton" onClick={() => setSidebarOpen(true)} aria-label="Hiện sidebar"><PanelLeft size={19} /></button> : null}
          <button className="traceButton" onClick={() => setShowStream((value) => !value)} type="button" aria-pressed={showStream}>
            <Activity size={17} /> {showStream ? "Ẩn luồng" : "Hiện luồng"}
          </button>
          {isSending ? <span className="loader" aria-label="Đang xử lý" /> : null}
        </header>
        <div className="messages" ref={scrollRef}>
          {messages.length === 0 ? <div className="empty">Hôm nay bạn có câu hỏi pháp lý gì?</div> : null}
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <div className="bubble">
                {message.role === "assistant" && showStream && (message.trace.length > 0 || message.stream.length > 0) ? (
                  <div className="streamBox">
                    <div className="streamHead">Luồng xử lý agent</div>
                    <div className="streamBody">
                      {message.trace.map((step, index) => (
                        <div className={`traceStep ${step.tone || "info"}`} key={`${step.title}-${index}`}>
                          <span>{index + 1}</span>
                          <div><strong>{step.title}</strong><p>{step.detail}</p></div>
                        </div>
                      ))}
                      {message.trace.length === 0 ? message.stream.map((line, index) => <div className="traceLine" key={`${line}-${index}`}>• {line}</div>) : null}
                    </div>
                  </div>
                ) : null}
                <div>{message.content}</div>
                {message.sources.length > 0 ? (
                  <div className="sources">
                    <strong>Nguồn</strong>
                    {message.sources.slice(0, 6).map((source) => <span key={source}>{source}</span>)}
                  </div>
                ) : null}
              </div>
            </article>
          ))}
          <div ref={bottomRef} className="bottomAnchor" />
        </div>

        <div className={sidebarOpen ? "composerWrap" : "composerWrap full"}>
          <form className="composer" onSubmit={onSubmit}>
            <button className="iconButton" type="button" onClick={newChat} aria-label="Đoạn chat mới"><SquarePen size={20} /></button>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submitChat(input);
                }
              }}
              rows={1}
              placeholder="Hỏi bất kỳ điều gì"
            />
            <button className="sendButton" disabled={isSending || !input.trim()} type="submit" aria-label="Gửi"><Send size={18} /></button>
          </form>
        </div>
      </section>
    </main>
  );
}
