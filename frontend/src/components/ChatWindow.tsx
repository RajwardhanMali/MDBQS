import { useEffect, useMemo, useRef } from 'react';
import { Cable, Sparkles } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { useQuery } from '../hooks/useQuery';
import UserMessageBubble from './UserMessageBubble';
import AssistantMessageBubble from './AssistantMessageBubble';
import QueryInput from './QueryInput';
import LoadingIndicator from './LoadingIndicator';
import SourcePicker from './SourcePicker';
import SchemaSearchPanel from './SchemaSearchPanel';

const ChatWindow = () => {
  const bootstrapping = useChatStore((state) => state.bootstrapping);
  const bootstrap = useChatStore((state) => state.bootstrap);
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const sessions = useChatStore((state) => state.sessions);
  const messagesBySession = useChatStore((state) => state.messagesBySession);
  const sendingMessage = useChatStore((state) => state.sendingMessage);
  const error = useChatStore((state) => state.error);
  const { execute } = useQuery();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const currentSession = useMemo(
    () => sessions.find((session) => session.session_id === currentSessionId) ?? null,
    [currentSessionId, sessions]
  );

  const messages = currentSessionId ? messagesBySession[currentSessionId] ?? [] : [];

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sendingMessage]);

  return (
    <div className="grid h-full min-h-0 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_24rem]">
      <section className="flex min-h-0 flex-col border-r border-border/60">
        <div className="border-b border-border/60 bg-card/60 px-4 py-4 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Chat Over Connected Data</p>
              <h2 className="font-serif text-xl text-foreground">
                {currentSession?.title || 'New chat session'}
              </h2>
            </div>
            <div className="hidden rounded-full border border-border/70 bg-background/80 px-3 py-1 text-xs text-muted-foreground md:block">
              {currentSession?.active_server_ids.length ?? 0} active sources
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-5xl px-4 py-6">
            {bootstrapping ? (
              <div className="flex min-h-[60vh] items-center justify-center">
                <LoadingIndicator label="Preparing the workspace" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex min-h-[65vh] items-center justify-center">
                <div className="w-full max-w-3xl rounded-[2rem] border border-border/70 bg-[radial-gradient(circle_at_top_left,_rgba(221,107,32,0.12),_transparent_40%),linear-gradient(135deg,rgba(14,116,144,0.12),rgba(255,255,255,0.65))] p-8 shadow-sm dark:bg-[radial-gradient(circle_at_top_left,_rgba(251,146,60,0.16),_transparent_35%),linear-gradient(135deg,rgba(12,74,110,0.35),rgba(15,23,42,0.9))]">
                  <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/12 text-primary">
                    <Cable className="h-7 w-7" />
                  </div>
                  <h3 className="font-serif text-3xl text-foreground">Ask across connected sources</h3>
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
                    The workspace is session-based, source-aware, and result-shape agnostic. Ask a question, inspect the result sets, then open explain or trace details when you need to verify how the answer was produced.
                  </p>
                  <div className="mt-6 flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span className="rounded-full border border-border/70 bg-background/70 px-3 py-1">Session replay</span>
                    <span className="rounded-full border border-border/70 bg-background/70 px-3 py-1">Source selection</span>
                    <span className="rounded-full border border-border/70 bg-background/70 px-3 py-1">Generic result sets</span>
                    <span className="rounded-full border border-border/70 bg-background/70 px-3 py-1">Trace + explain</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((message) =>
                  message.role === 'user' ? (
                    <UserMessageBubble key={message.message_id} message={message} />
                  ) : (
                    <AssistantMessageBubble key={message.message_id} message={message} />
                  )
                )}
                {sendingMessage && <LoadingIndicator label="Querying selected sources" />}
              </div>
            )}

            {error && (
              <div className="mt-4 rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {error}
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        <div className="border-t border-border/60 bg-background/90 p-4 backdrop-blur">
          <QueryInput onSubmit={execute} disabled={bootstrapping || sendingMessage} />
        </div>
      </section>

      <aside className="hidden min-h-0 flex-col overflow-y-auto bg-muted/30 xl:flex">
        <div className="space-y-6 p-4">
          <div className="rounded-3xl border border-border/70 bg-card/80 p-4 shadow-sm">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
              <Sparkles className="h-4 w-4 text-primary" />
              Workspace tools
            </div>
            <p className="text-sm leading-6 text-muted-foreground">
              Choose active sources for this session and inspect schema fields before you ask the next question.
            </p>
          </div>
          <SourcePicker />
          <SchemaSearchPanel />
        </div>
      </aside>
    </div>
  );
};

export default ChatWindow;
