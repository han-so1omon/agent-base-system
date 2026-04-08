'use client';

import { useChat } from '@ai-sdk/react';
import { FormEvent, useMemo, useState } from 'react';

type AssistantMetadata = {
  citations?: Array<{ source: string; snippet: string }>;
  debug?: Record<string, number>;
  thread_id?: string;
};

export default function Page() {
  const [threadId, setThreadId] = useState('play-thread');
  const [assistantMetadata, setAssistantMetadata] = useState<AssistantMetadata>({});

  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    error,
    status,
  } = useChat({
    api: '/api/chat',
    streamProtocol: 'text',
    maxSteps: 1,
    experimental_prepareRequestBody: ({ messages }) => ({
      threadId,
      messages: messages.map(message => ({
        role: message.role,
        parts: [{ type: 'text', text: extractMessageText(message.content) }],
      })),
    }),
    onResponse(response) {
      setAssistantMetadata({
        thread_id: response.headers.get('x-thread-id') ?? threadId,
        citations: parseJsonHeader(response.headers.get('x-citations')) ?? [],
        debug: parseJsonHeader(response.headers.get('x-debug')) ?? {},
      });
    },
  });

  const chatMessages = useMemo(
    () =>
      messages.map(message => ({
        id: message.id,
        role: message.role,
        text: extractMessageText(message.content),
      })),
    [messages],
  );

  const isLoading = status === 'submitted' || status === 'streaming';

  return (
    <main style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.5fr) minmax(280px, 0.8fr)', gap: 24 }}>
      <section
        style={{
          minHeight: 'calc(100vh - 48px)',
          border: '1px solid var(--line)',
          background: 'var(--panel)',
          boxShadow: 'var(--shadow)',
          backdropFilter: 'blur(18px)',
          display: 'grid',
          gridTemplateRows: 'auto 1fr auto',
        }}
      >
        <header style={{ padding: 24, borderBottom: '1px solid var(--line)' }}>
          <div style={{ color: 'var(--accent)', fontSize: 12, letterSpacing: '0.28em', textTransform: 'uppercase' }}>
            Base Agent System
          </div>
          <h1 style={{ margin: '14px 0 12px', fontSize: 'clamp(2rem, 4vw, 4.4rem)', lineHeight: 0.95, fontWeight: 500 }}>
            Operator Chat
          </h1>
          <p style={{ margin: 0, maxWidth: 640, color: 'var(--muted)', fontSize: 16, lineHeight: 1.6 }}>
            Query retrieval, memory, and persistence through the existing FastAPI backend. Watch citations and debug hits change as the thread ID evolves.
          </p>
        </header>

        <div style={{ padding: 24, overflowY: 'auto', display: 'grid', gap: 16 }}>
          {chatMessages.length === 0 ? (
            <div style={{ border: '1px dashed var(--line)', padding: 20, background: 'rgba(255,255,255,0.02)' }}>
              <div style={{ color: 'var(--accent)', marginBottom: 8 }}>Try one of these</div>
              <div style={{ color: 'var(--muted)', lineHeight: 1.7 }}>
                What does the markdown ingestion service do?<br />
                Remember that my preferred deployment target is Kubernetes.<br />
                What is my preferred deployment target?
              </div>
            </div>
          ) : null}

          {chatMessages.map(message => (
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
              <div style={{ color: 'var(--accent)', fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 10 }}>
                {message.role === 'user' ? 'Operator' : 'System'}
              </div>
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{message.text}</div>
            </article>
          ))}
        </div>

        <form
          onSubmit={(event: FormEvent<HTMLFormElement>) => {
            event.preventDefault();
            handleSubmit(event);
          }}
          style={{ borderTop: '1px solid var(--line)', padding: 20, display: 'grid', gap: 12 }}
        >
          <label style={{ display: 'grid', gap: 8 }}>
            <span style={{ color: 'var(--muted)', fontSize: 13, letterSpacing: '0.14em', textTransform: 'uppercase' }}>Thread ID</span>
            <input
              value={threadId}
              onChange={event => setThreadId(event.target.value)}
              style={{
                width: '100%',
                border: '1px solid var(--line)',
                background: 'var(--panel-strong)',
                color: 'var(--text)',
                padding: '12px 14px',
              }}
            />
          </label>

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
          {error ? <div style={{ color: '#ff8b8b' }}>{error.message}</div> : null}
        </form>
      </section>

      <aside
        style={{
          minHeight: 'calc(100vh - 48px)',
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
          <div style={{ color: 'var(--text)', fontSize: 20 }}>{assistantMetadata.thread_id ?? threadId}</div>
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

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ border: '1px solid var(--line)', padding: 14, background: 'rgba(255,255,255,0.02)' }}>
      <div style={{ color: 'var(--muted)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 28 }}>{value}</div>
    </div>
  );
}
