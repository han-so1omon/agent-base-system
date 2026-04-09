'use client';

import { useChat } from '@ai-sdk/react';
import { FormEvent, UIEvent, useEffect, useRef, useState } from 'react';

type Citation = {
  source: string;
  snippet: string;
};

type AssistantMetadata = {
  citations?: Citation[];
  debug?: Record<string, number>;
  thread_id?: string;
};

type ThreadSummary = {
  thread_id: string;
  preview: string;
};

type AgentRunMetadata = {
  used_tools: boolean;
  tool_call_count: number;
  tools_used: string[];
};

type InteractionMessage = {
  id: string;
  thread_id: string;
  kind: 'user' | 'agent_run';
  content: string;
  created_at: string;
  metadata?: AgentRunMetadata | null;
};

type InteractionPage = {
  messages: InteractionMessage[];
  has_more: boolean;
  next_before: { before_ts: string; before_id: string } | null;
};

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  metadata?: AgentRunMetadata | null;
  source: 'history' | 'live';
};

const INITIAL_ASSISTANT_METADATA: AssistantMetadata = {};
const INITIAL_INTERACTION_PAGE: InteractionPage = {
  messages: [],
  has_more: false,
  next_before: null,
};

export default function Page() {
  const [threadId, setThreadId] = useState<string | undefined>();
  const [assistantMetadata, setAssistantMetadata] = useState<AssistantMetadata>(INITIAL_ASSISTANT_METADATA);
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [historyPage, setHistoryPage] = useState<InteractionPage>(INITIAL_INTERACTION_PAGE);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [threadStatus, setThreadStatus] = useState<'idle' | 'loading'>('idle');
  const [historyStatus, setHistoryStatus] = useState<'idle' | 'loading-more'>('idle');
  const historyContainerRef = useRef<HTMLDivElement | null>(null);
  const pendingThreadIdRef = useRef<string | undefined>(undefined);

  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    error,
    status,
  } = useChat({
    api: '/api/chat',
    headers: {
      accept: 'text/plain',
    },
    streamProtocol: 'text',
    maxSteps: 1,
    experimental_prepareRequestBody: ({ messages: nextMessages }) => ({
      threadId: pendingThreadIdRef.current ?? threadId ?? createThreadId(),
      messages: nextMessages.map(message => ({
        role: message.role,
        parts: [{ type: 'text', text: extractMessageText(message.content) }],
      })),
    }),
    onResponse(response) {
      const resolvedThreadId = response.headers.get('x-thread-id') ?? threadId ?? undefined;
      pendingThreadIdRef.current = undefined;
      if (resolvedThreadId) {
        setThreadId(resolvedThreadId);
      }
      setAssistantMetadata({
        thread_id: resolvedThreadId,
        citations: parseJsonHeader(response.headers.get('x-citations')) ?? [],
        debug: parseJsonHeader(response.headers.get('x-debug')) ?? {},
      });
      void loadThreads();
    },
  });

  useEffect(() => {
    void loadThreads();
  }, []);

  useEffect(() => {
    if (!threadId) {
      setHistoryPage(INITIAL_INTERACTION_PAGE);
      setHistoryError(null);
      return;
    }
    void loadThreadInteractions(threadId);
  }, [threadId]);

  const liveMessages: ChatMessage[] = messages.map(message => ({
    id: message.id,
    role: message.role === 'user' ? 'user' : 'assistant',
    text: extractMessageText(message.content),
    metadata: undefined,
    source: 'live',
  }));

  const historyMessages = historyPage.messages.map(mapInteractionToChatMessage);
  const displayedMessages = mergeMessages(historyMessages, liveMessages);

  const activeThreadId = assistantMetadata.thread_id ?? threadId;
  const isLoading = status === 'submitted' || status === 'streaming';

  async function loadThreads() {
    setThreadStatus('loading');
    try {
      const response = await fetch('/threads');
      if (!response.ok) {
        throw new Error(`Failed to load threads (${response.status})`);
      }
      const nextThreads = (await response.json()) as ThreadSummary[];
      setThreads(nextThreads);
      if (!threadId && nextThreads.length > 0) {
        setThreadId(nextThreads[0].thread_id);
      }
    } catch (loadError) {
      setHistoryError(loadError instanceof Error ? loadError.message : 'Failed to load threads');
    } finally {
      setThreadStatus('idle');
    }
  }

  async function loadThreadInteractions(nextThreadId: string, cursor?: { before_ts: string; before_id: string }) {
    setHistoryStatus(cursor ? 'loading-more' : 'idle');
    setHistoryError(null);
    const params = new URLSearchParams();
    if (cursor) {
      params.set('before_ts', cursor.before_ts);
      params.set('before_id', cursor.before_id);
    }

    try {
      const path = params.size > 0
        ? `/threads/${encodeURIComponent(nextThreadId)}/interactions?${params.toString()}`
        : `/threads/${encodeURIComponent(nextThreadId)}/interactions`;
      const response = await fetch(path);
      if (!response.ok) {
        throw new Error(`Failed to load interactions (${response.status})`);
      }
      const page = (await response.json()) as InteractionPage;
      setHistoryPage(current => ({
        messages: cursor ? [...page.messages, ...current.messages] : page.messages,
        has_more: page.has_more,
        next_before: page.next_before,
      }));
    } catch (loadError) {
      setHistoryError(loadError instanceof Error ? loadError.message : 'Failed to load interactions');
    } finally {
      setHistoryStatus('idle');
    }
  }

  async function handleHistoryScroll(event: UIEvent<HTMLDivElement>) {
    const element = event.currentTarget;
    if (element.scrollTop > 48 || !threadId || !historyPage.has_more || !historyPage.next_before || historyStatus !== 'idle') {
      return;
    }
    const previousHeight = element.scrollHeight;
    await loadThreadInteractions(threadId, historyPage.next_before);
    requestAnimationFrame(() => {
      if (!historyContainerRef.current) {
        return;
      }
      historyContainerRef.current.scrollTop = historyContainerRef.current.scrollHeight - previousHeight;
    });
  }

  return (
    <main style={{ display: 'grid', gridTemplateColumns: '320px minmax(0, 1fr) 320px', gap: 24 }}>
      <aside
        style={{
          height: 'calc(100vh - 48px)',
          border: '1px solid var(--line)',
          background: 'var(--panel)',
          boxShadow: 'var(--shadow)',
          backdropFilter: 'blur(18px)',
          padding: 24,
          display: 'grid',
          gridTemplateRows: 'auto 1fr auto',
          gap: 18,
          overflow: 'hidden',
        }}
      >
        <div>
          <div style={{ color: 'var(--accent)', fontSize: 12, letterSpacing: '0.24em', textTransform: 'uppercase', marginBottom: 12 }}>
            Recent Threads
          </div>
          <div style={{ color: 'var(--muted)', lineHeight: 1.6, marginBottom: 16 }}>
            New thread starts on first message. Reopen any thread to continue the same LangGraph execution path.
          </div>
          <button
            type="button"
            onClick={() => {
              setThreadId(undefined);
              setAssistantMetadata(INITIAL_ASSISTANT_METADATA);
            }}
            style={threadActionButtonStyle}
          >
            Start Empty Draft
          </button>
        </div>

        <div style={{ display: 'grid', gap: 10, overflowY: 'auto', minHeight: 0, alignContent: 'start' }}>
          {threads.map(thread => {
            const isActive = thread.thread_id === activeThreadId;
            return (
              <button
                key={thread.thread_id}
                type="button"
                onClick={() => setThreadId(thread.thread_id)}
                style={{
                  ...threadCardStyle,
                  background: isActive ? 'rgba(240,201,107,0.12)' : 'rgba(255,255,255,0.02)',
                  borderColor: isActive ? 'rgba(240,201,107,0.45)' : 'var(--line)',
                }}
              >
                <div style={{ color: 'var(--text)', fontSize: 15, marginBottom: 8, lineHeight: 1.4 }}>{thread.preview}</div>
                <div style={{ color: 'var(--muted)', fontSize: 13, lineHeight: 1.5 }}>{thread.thread_id}</div>
              </button>
            );
          })}
          {threads.length === 0 ? <div style={{ color: 'var(--muted)', lineHeight: 1.6 }}>No saved threads yet.</div> : null}
        </div>

        <div style={{ color: 'var(--muted)', fontSize: 13 }}>
          {threadStatus === 'loading' ? 'Refreshing thread list...' : 'Thread browser uses /threads and keeps /api/chat as the write path.'}
        </div>
      </aside>

      <section
        style={{
          height: 'calc(100vh - 48px)',
          border: '1px solid var(--line)',
          background: 'var(--panel)',
          boxShadow: 'var(--shadow)',
          backdropFilter: 'blur(18px)',
          display: 'grid',
          gridTemplateRows: 'auto 1fr auto',
          minWidth: 0,
          overflow: 'hidden',
        }}
      >
        <header style={{ padding: 24, borderBottom: '1px solid var(--line)' }}>
          <div style={{ color: 'var(--accent)', fontSize: 12, letterSpacing: '0.28em', textTransform: 'uppercase' }}>
            Base Agent System
          </div>
          <h1 style={{ margin: '14px 0 12px', fontSize: 'clamp(2rem, 4vw, 4.4rem)', lineHeight: 0.95, fontWeight: 500 }}>
            Operator Chat
          </h1>
          <p style={{ margin: 0, maxWidth: 680, color: 'var(--muted)', fontSize: 16, lineHeight: 1.6 }}>
            Browse recent threads, reopen older runs, and keep tool-aware answers streaming through the same FastAPI adapter.
          </p>
        </header>

        <div
          ref={historyContainerRef}
          onScroll={handleHistoryScroll}
          style={{ padding: 24, overflowY: 'auto', display: 'grid', gap: 16, minHeight: 0 }}
        >
          {historyPage.has_more ? (
            <div style={historyStatus === 'loading-more' ? loadingNoticeStyle : paginationNoticeStyle}>
              {historyStatus === 'loading-more' ? 'Loading older interactions...' : 'Scroll upward to load older interactions'}
            </div>
          ) : null}

          {displayedMessages.length === 0 ? (
            <div style={{ border: '1px dashed var(--line)', padding: 20, background: 'rgba(255,255,255,0.02)' }}>
              <div style={{ color: 'var(--accent)', marginBottom: 8 }}>Try one of these</div>
              <div style={{ color: 'var(--muted)', lineHeight: 1.7 }}>
                What does the markdown ingestion service do?<br />
                Remember that my preferred deployment target is Kubernetes.<br />
                What is my preferred deployment target?
              </div>
            </div>
          ) : null}

          {displayedMessages.map(message => (
            <article
              key={message.id}
              style={{
                justifySelf: message.role === 'user' ? 'end' : 'start',
                maxWidth: '78%',
                padding: '16px 18px',
                border: '1px solid var(--line)',
                background: message.role === 'user' ? 'var(--user)' : 'var(--assistant)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
                <div style={{ color: 'var(--accent)', fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase' }}>
                  {message.role === 'user' ? 'Operator' : 'System'}
                </div>
                {message.metadata?.used_tools ? <ToolBadge metadata={message.metadata} /> : null}
              </div>
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{message.text}</div>
            </article>
          ))}

          {historyError ? <div style={{ color: '#ff8b8b' }}>{historyError}</div> : null}
        </div>

        <form
          onSubmit={(event: FormEvent<HTMLFormElement>) => {
            event.preventDefault();
            if (!threadId) {
              const generatedThreadId = createThreadId();
              pendingThreadIdRef.current = generatedThreadId;
              setThreadId(generatedThreadId);
            }
            handleSubmit(event);
          }}
          style={{ borderTop: '1px solid var(--line)', padding: 20, display: 'grid', gap: 12 }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12 }}>
            <input
              name="prompt"
              value={input}
              onChange={handleInputChange}
              placeholder="Ask the system something real."
              disabled={isLoading}
              style={{
                width: '100%',
                border: '1px solid var(--line)',
                background: 'var(--panel-strong)',
                color: 'var(--text)',
                padding: '14px 16px',
              }}
            />
            <button
              type="submit"
              disabled={isLoading}
              style={{
                border: '1px solid rgba(240, 201, 107, 0.45)',
                background: 'linear-gradient(135deg, rgba(211,190,142,0.24), rgba(240,201,107,0.08))',
                color: 'var(--text)',
                padding: '0 20px',
                minHeight: 50,
                cursor: isLoading ? 'not-allowed' : 'pointer',
              }}
            >
              {isLoading ? 'Working' : 'Send'}
            </button>
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 13 }}>
            Active thread: <code>{activeThreadId ?? 'new thread pending first message'}</code>
          </div>
          {error ? <div style={{ color: '#ff8b8b' }}>{error.message}</div> : null}
        </form>
      </section>

      <aside
        style={{
          height: 'calc(100vh - 48px)',
          border: '1px solid var(--line)',
          background: 'var(--panel)',
          boxShadow: 'var(--shadow)',
          backdropFilter: 'blur(18px)',
          padding: 24,
          display: 'grid',
          alignContent: 'start',
          gap: 20,
        }}
      >
        <section>
          <div style={{ color: 'var(--accent)', fontSize: 12, letterSpacing: '0.24em', textTransform: 'uppercase', marginBottom: 12 }}>
            Thread
          </div>
          <div style={{ color: 'var(--text)', fontSize: 20 }}>{activeThreadId ?? 'Awaiting first operator prompt'}</div>
        </section>

        <section>
          <div style={{ color: 'var(--accent)', fontSize: 12, letterSpacing: '0.24em', textTransform: 'uppercase', marginBottom: 12 }}>
            Debug
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            <Metric label="Document Hits" value={assistantMetadata.debug?.document_hits ?? 0} />
            <Metric label="Memory Hits" value={assistantMetadata.debug?.memory_hits ?? 0} />
          </div>
        </section>

        <section>
          <div style={{ color: 'var(--accent)', fontSize: 12, letterSpacing: '0.24em', textTransform: 'uppercase', marginBottom: 12 }}>
            Citations
          </div>
          <div style={{ display: 'grid', gap: 12 }}>
            {(assistantMetadata.citations ?? []).length === 0 ? (
              <div style={{ color: 'var(--muted)', lineHeight: 1.6 }}>No citations yet. Ask a retrieval-heavy question after ingesting docs.</div>
            ) : (
              assistantMetadata.citations?.map(citation => (
                <article key={`${citation.source}-${citation.snippet}`} style={{ border: '1px solid var(--line)', padding: 14, background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ color: 'var(--text)', marginBottom: 8 }}>{citation.source}</div>
                  <div style={{ color: 'var(--muted)', lineHeight: 1.6 }}>{citation.snippet}</div>
                </article>
              ))
            )}
          </div>
        </section>
      </aside>
    </main>
  );
}

function mapInteractionToChatMessage(message: InteractionMessage): ChatMessage {
  return {
    id: message.id,
    role: message.kind === 'user' ? 'user' : 'assistant',
    text: message.content,
    metadata: message.metadata,
    source: 'history',
  };
}

function createThreadId(): string {
  return `thread-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function extractMessageText(content: unknown): string {
  if (typeof content === 'string') {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map(part => {
        if (typeof part === 'string') {
          return part;
        }
        if (part && typeof part === 'object' && 'text' in part) {
          return String((part as { text?: unknown }).text ?? '');
        }
        return '';
      })
      .join('')
      .trim();
  }
  return '';
}

function parseJsonHeader<T>(value: string | null): T | undefined {
  if (!value) {
    return undefined;
  }
  try {
    return JSON.parse(value) as T;
  } catch {
    return undefined;
  }
}

function mergeMessages(historyMessages: ChatMessage[], liveMessages: ChatMessage[]): ChatMessage[] {
  if (liveMessages.length === 0) {
    return historyMessages;
  }

  const liveMessageKeys = new Set(liveMessages.map(message => `${message.role}:${message.text}`));
  const persistedMessages = historyMessages.filter(message => !liveMessageKeys.has(`${message.role}:${message.text}`));

  return [...persistedMessages, ...liveMessages];
}

function ToolBadge({ metadata }: { metadata: AgentRunMetadata }) {
  const label = metadata.tool_call_count === 1 ? '1 tool call' : `${metadata.tool_call_count} tool calls`;
  const detail = metadata.tools_used.join(', ');
  return (
    <div title={detail} style={toolBadgeStyle}>
      Tools used: {label}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ border: '1px solid var(--line)', padding: 14, background: 'rgba(255,255,255,0.02)' }}>
      <div style={{ color: 'var(--muted)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 28 }}>{value}</div>
    </div>
  );
}

const threadActionButtonStyle = {
  width: '100%',
  border: '1px solid rgba(240, 201, 107, 0.35)',
  background: 'rgba(240,201,107,0.06)',
  color: 'var(--text)',
  padding: '12px 14px',
  textAlign: 'left' as const,
  cursor: 'pointer',
};

const threadCardStyle = {
  width: '100%',
  border: '1px solid var(--line)',
  padding: 14,
  textAlign: 'left' as const,
  color: 'inherit',
  cursor: 'pointer',
};

const toolBadgeStyle = {
  border: '1px solid rgba(240, 201, 107, 0.35)',
  color: 'var(--accent)',
  fontSize: 11,
  letterSpacing: '0.08em',
  textTransform: 'uppercase' as const,
  padding: '4px 8px',
  whiteSpace: 'nowrap' as const,
};

const paginationNoticeStyle = {
  justifySelf: 'center' as const,
  color: 'var(--muted)',
  fontSize: 12,
  letterSpacing: '0.12em',
  textTransform: 'uppercase' as const,
};

const loadingNoticeStyle = {
  ...paginationNoticeStyle,
  color: 'var(--accent)',
};
