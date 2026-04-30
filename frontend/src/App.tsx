import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState, useRef, useEffect, useCallback } from "react";
import {
  askQuestion,
  ApiError,
  listConversations,
  getConversation,
  newConversationId,
} from "./api";
import type {
  ChatResponse,
  ToolTraceEntry,
  ConversationSummary,
} from "./api";
import Charts from "./Chart";

interface Message {
  role: "user" | "assistant" | "error";
  text: string;
  trace?: ToolTraceEntry[];
  sources?: string[];
}

const EXAMPLES = [
  "Which titles performed best in 2025?",
  "Why is Stellar Run trending recently?",
  "Compare Dark Orbit vs Last Kingdom.",
  "Which city had the strongest engagement last month?",
  "What explains weak comedy performance?",
  "What recommendations would you give for leadership?",
];

const GENRES = [
  "", "Drama", "Comedy", "Sci-Fi", "Action", "Thriller",
  "Romance", "Documentary", "Horror",
];
const CITIES = [
  "", "Mumbai", "Delhi", "Bangalore", "London", "New York",
  "Tokyo", "Paris", "Berlin", "Seoul", "Sao Paulo",
];

export default function App() {
  const [conversationId, setConversationId] = useState<string>(() =>
    newConversationId()
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeTrace, setActiveTrace] = useState<ToolTraceEntry[] | null>(null);
  const [activeSources, setActiveSources] = useState<string[]>([]);
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [genre, setGenre] = useState("");
  const [city, setCity] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const refreshHistory = useCallback(() => {
    listConversations()
      .then(setHistory)
      .catch(() => {/* sidebar is optional */});
  }, []);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  function applyFilters(question: string): string {
    const parts: string[] = [];
    if (genre) parts.push(`for genre ${genre}`);
    if (city) parts.push(`in ${city}`);
    if (start && end) parts.push(`between ${start} and ${end}`);
    else if (start) parts.push(`from ${start}`);
    else if (end) parts.push(`up to ${end}`);
    if (parts.length === 0) return question;
    return `${question} (${parts.join(", ")})`;
  }

  async function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    const scoped = applyFilters(trimmed);

    setMessages((prev) => [...prev, { role: "user", text: scoped }]);
    setInput("");
    setLoading(true);

    try {
      const resp: ChatResponse = await askQuestion(scoped, conversationId);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: resp.answer,
          trace: resp.trace,
          sources: resp.sources,
        },
      ]);
      setActiveTrace(resp.trace);
      setActiveSources(resp.sources);
      refreshHistory();
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? `${err.status}: ${err.message}`
          : err instanceof Error
          ? err.message
          : "Unknown error";
      setMessages((prev) => [
        ...prev,
        { role: "error", text: `Request failed: ${detail}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function startNewChat() {
    setConversationId(newConversationId());
    setMessages([]);
    setActiveTrace(null);
    setActiveSources([]);
  }

  async function loadConversation(id: string) {
    try {
      const detail = await getConversation(id);
      const restored: Message[] = [];
      for (const turn of detail.turns) {
        restored.push({ role: "user", text: turn.question });
        restored.push({
          role: "assistant",
          text: turn.answer,
          trace: turn.trace,
          sources: turn.sources,
        });
      }
      setConversationId(id);
      setMessages(restored);
      const last = detail.turns[detail.turns.length - 1];
      setActiveTrace(last?.trace ?? null);
      setActiveSources(last?.sources ?? []);
    } catch {
      // ignore
    }
  }

  function clearFilters() {
    setGenre("");
    setCity("");
    setStart("");
    setEnd("");
  }

  return (
    <div className="h-screen flex flex-col bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-3">
        <h1 className="text-lg font-semibold">Secure AI Insights Assistant</h1>
        <p className="text-xs text-slate-500">
          Internal analytics over movies, viewers, marketing, and reports
        </p>
      </header>

      <div className="flex-1 grid grid-cols-[240px_1fr_360px] overflow-hidden">
        {/* History sidebar */}
        <aside className="border-r border-slate-200 bg-white overflow-y-auto">
          <div className="p-3 border-b border-slate-200">
            <button
              onClick={startNewChat}
              className="w-full text-sm bg-slate-900 text-white rounded-md py-2 hover:bg-slate-700"
            >
              + New chat
            </button>
          </div>
          <ul className="p-2 space-y-1">
            {history.length === 0 && (
              <li className="text-xs text-slate-400 px-2 py-1">
                No past conversations yet.
              </li>
            )}
            {history.map((c) => {
              const isActive = c.conversation_id === conversationId;
              return (
                <li key={c.conversation_id}>
                  <button
                    onClick={() => loadConversation(c.conversation_id)}
                    className={`w-full text-left text-xs rounded px-2 py-1.5 leading-snug ${
                      isActive
                        ? "bg-slate-100 text-slate-900"
                        : "text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    <div className="truncate font-medium">
                      {c.first_question}
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {c.turn_count} turn{c.turn_count === 1 ? "" : "s"} ·{" "}
                      {new Date(c.last_at).toLocaleDateString()}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        {/* Chat column */}
        <main className="flex flex-col overflow-hidden">
          {/* Filters bar */}
          <div className="border-b border-slate-200 bg-white px-6 py-3 flex flex-wrap items-center gap-3">
            <span className="text-xs text-slate-500 font-medium uppercase tracking-wide">
              Filters
            </span>
            <select
              value={genre}
              onChange={(e) => setGenre(e.target.value)}
              className="text-xs border border-slate-300 rounded px-2 py-1"
            >
              {GENRES.map((g) => (
                <option key={g} value={g}>
                  {g || "Any genre"}
                </option>
              ))}
            </select>
            <select
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="text-xs border border-slate-300 rounded px-2 py-1"
            >
              {CITIES.map((c) => (
                <option key={c} value={c}>
                  {c || "Any city"}
                </option>
              ))}
            </select>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="text-xs border border-slate-300 rounded px-2 py-1"
            />
            <span className="text-xs text-slate-400">to</span>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="text-xs border border-slate-300 rounded px-2 py-1"
            />
            {(genre || city || start || end) && (
              <button
                onClick={clearFilters}
                className="text-xs text-slate-500 hover:text-slate-900"
              >
                clear
              </button>
            )}
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="max-w-2xl">
                <h2 className="text-sm font-medium text-slate-700 mb-3">
                  Try one of these:
                </h2>
                <div className="grid grid-cols-1 gap-2">
                  {EXAMPLES.map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      className="text-left text-sm bg-white border border-slate-200 rounded-md px-3 py-2 hover:border-slate-400 hover:bg-slate-100"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <MessageBubble
                key={i}
                message={m}
                onSelect={() => {
                  if (m.trace) setActiveTrace(m.trace);
                  if (m.sources) setActiveSources(m.sources);
                }}
              />
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <span className="inline-block h-2 w-2 rounded-full bg-slate-400 animate-pulse" />
                thinking…
              </div>
            )}
          </div>

          <div className="border-t border-slate-200 bg-white px-6 py-3">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about titles, viewers, marketing, regions…"
                className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:border-slate-500"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="px-4 py-2 bg-slate-900 text-white text-sm rounded-md disabled:opacity-50 hover:bg-slate-700"
              >
                Send
              </button>
            </form>
          </div>
        </main>

        {/* Right rail: insights panel */}
        <aside className="border-l border-slate-200 bg-white overflow-y-auto">
          <InsightsPanel trace={activeTrace} sources={activeSources} />
        </aside>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  onSelect,
}: {
  message: Message;
  onSelect: () => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-2xl bg-slate-900 text-white rounded-lg px-4 py-2 text-sm">
          {message.text}
        </div>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div className="max-w-2xl bg-rose-50 border border-rose-200 text-rose-900 rounded-lg px-4 py-2 text-sm">
        {message.text}
      </div>
    );
  }

  // Compose data-source pills from both PDF citations and structured tools used.
const pills: string[] = [];

  // PDF sources from search_documents.
  for (const s of message.sources ?? []) {
    pills.push(`PDF: ${s}`);
  }

  // Tables and CSVs touched, derived from each tool call's args.
  const trace = message.trace ?? [];
  const tables = new Set<string>();
  const csvs = new Set<string>();
  for (const t of trace) {
    if (!t.ok) continue;
    if (t.tool === "query_metrics") {
      const args = t.args as Record<string, unknown>;
      const metric = args.metric;
      tables.add(metric === "avg_rating" ? "reviews" : "watch_activity");
      if (args.group_by === "genre" || args.group_by === "movie" ||
          args.genre || args.movie_title) {
        tables.add("movies");
      }
      if (args.group_by === "city" || args.group_by === "country" ||
          args.group_by === "age_band" || args.city || args.country) {
        tables.add("viewers");
      }
    }
    if (t.tool === "compute_aggregate") {
      const file = (t.args as Record<string, unknown>)?.file;
      if (typeof file === "string") csvs.add(`${file}.csv`);
    }
  }
  if (tables.size > 0) {
    pills.push(`SQL: ${[...tables].join(", ")}`);
  }
  for (const c of csvs) {
    pills.push(`CSV: ${c}`);
  }

  return (
    <div onClick={onSelect} className="max-w-2xl cursor-pointer">
      <div className="bg-white border border-slate-200 rounded-lg px-4 py-3 text-sm leading-relaxed [&_strong]:font-semibold [&_p]:my-2 [&_ol]:list-decimal [&_ol]:ml-5 [&_ul]:list-disc [&_ul]:ml-5 [&_li]:my-1">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {message.text}
        </ReactMarkdown>
      </div>
      {pills.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {pills.map((s) => (
            <span
              key={s}
              className="text-xs bg-slate-100 border border-slate-200 rounded px-2 py-0.5 text-slate-600"
            >
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function InsightsPanel({
  trace,
  sources,
}: {
  trace: ToolTraceEntry[] | null;
  sources: string[];
}) {
  if (!trace || trace.length === 0) {
    return (
      <div className="p-4 text-xs text-slate-500">
        Visualizations, tool trace, and sources for the selected message
        will appear here.
      </div>
    );
  }

  return (
    <div className="p-4 space-y-6">
      <Charts trace={trace} />

      <section>
        <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wide mb-2">
          Tool calls ({trace.length})
        </h3>
        <ol className="space-y-2">
          {trace.map((step, i) => (
            <li
              key={i}
              className={`text-xs border rounded px-2 py-1.5 ${
                step.ok
                  ? "border-slate-200 bg-slate-50"
                  : "border-rose-200 bg-rose-50"
              }`}
            >
              <div className="font-mono font-medium">{step.tool}</div>
              <div className="text-slate-500 mt-0.5">
                {step.ok ? step.result_summary : step.error}
              </div>
              <details className="mt-1">
                <summary className="cursor-pointer text-slate-400">args</summary>
                <pre className="mt-1 text-[10px] overflow-x-auto">
                  {JSON.stringify(step.args, null, 2)}
                </pre>
              </details>
            </li>
          ))}
        </ol>
      </section>

      {sources.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wide mb-2">
            Sources
          </h3>
          <ul className="space-y-1">
            {sources.map((s) => (
              <li key={s} className="text-xs text-slate-600">
                {s}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}