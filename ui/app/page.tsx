"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Activity, MessageSquarePlus, PanelLeft, Search, Send, SquarePen } from "lucide-react";
import { parseSseChunk } from "@/lib/sse";
import type { ChatMessage, ChatStreamEvent } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const DEFAULT_DATABASE = process.env.NEXT_PUBLIC_DEFAULT_DATABASE || "default";

function createId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [showStream, setShowStream] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const current = window.localStorage.getItem("mscai_session_id") || createId();
    window.localStorage.setItem("mscai_session_id", current);
    setSessionId(current);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const chatTitles = useMemo(
    () => messages.filter((item) => item.role === "user").map((item) => item.content).slice(-12).reverse(),
    [messages],
  );
  const visibleChatTitles = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase();
    if (!keyword) return chatTitles;
    return chatTitles.filter((title) => title.toLowerCase().includes(keyword));
  }, [chatTitles, searchTerm]);

  function newChat() {
    const next = createId();
    window.localStorage.setItem("mscai_session_id", next);
    setSessionId(next);
    setMessages([]);
    setSearchTerm("");
  }

  function updateAssistant(id: string, updater: (message: ChatMessage) => ChatMessage) {
    setMessages((items) => items.map((item) => (item.id === id ? updater(item) : item)));
  }

  function handleStreamEvent(event: ChatStreamEvent, assistantId: string) {
    if (event.event === "status") {
      updateAssistant(assistantId, (message) => ({ ...message, stream: [...message.stream, event.data.message] }));
      return;
    }
    if (event.event === "error") {
      updateAssistant(assistantId, (message) => ({
        ...message,
        content: event.data.message || "Có lỗi khi gọi backend.",
        stream: [...message.stream, "Lỗi"],
      }));
      return;
    }
    if (event.event === "result") {
      const answer = event.data.answer;
      updateAssistant(assistantId, (message) => ({
        ...message,
        content: answer.answer || "Không có câu trả lời.",
        sources: answer.relevant_articles || [],
        stream: [...message.stream, "Đã nhận kết quả"],
      }));
      return;
    }
    if (event.event === "done") {
      updateAssistant(assistantId, (message) => ({ ...message, stream: [...message.stream, event.data.message] }));
    }
  }

  async function submitChat(question: string) {
    if (!question.trim() || isSending) return;
    const currentSessionId = sessionId || createId();
    if (!sessionId) {
      window.localStorage.setItem("mscai_session_id", currentSessionId);
      setSessionId(currentSessionId);
    }

    const userMessage: ChatMessage = {
      id: createId(),
      role: "user",
      content: question.trim(),
      stream: [],
      sources: [],
    };
    const assistantId = createId();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "Đang tạo câu trả lời...",
      stream: [],
      sources: [],
    };
    setMessages((items) => [...items, userMessage, assistantMessage]);
    setInput("");
    setIsSending(true);

    try {
      const response = await fetch(`${API_BASE}/api/v1/legal/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          message: question.trim(),
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
          if (event) handleStreamEvent(event, assistantId);
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không gọi được backend.";
      updateAssistant(assistantId, (item) => ({ ...item, content: message, stream: [...item.stream, "Lỗi kết nối"] }));
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
            {visibleChatTitles.length === 0 ? <span className="muted">Không có đoạn chat</span> : null}
            {visibleChatTitles.map((title, index) => <button className="chatLink" key={`${title}-${index}`}>{title}</button>)}
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
                {message.role === "assistant" && message.stream.length > 0 && showStream ? (
                  <div className="streamBox">
                    <div className="streamHead">Luồng xử lý agent</div>
                    <div className="streamBody">
                      {message.stream.map((line, index) => <div key={`${line}-${index}`}>• {line}</div>)}
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
