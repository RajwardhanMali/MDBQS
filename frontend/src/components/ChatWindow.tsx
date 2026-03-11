import { useEffect, useRef } from 'react';
import { Database } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { useQuery } from '../hooks/useQuery';
import UserMessageBubble from './UserMessageBubble';
import AssistantMessageBubble from './AssistantMessageBubble';
import QueryInput from './QueryInput';
import LoadingIndicator from './LoadingIndicator';

const ChatWindow = () => {
  const messages = useChatStore((state) => state.messages);
  const loading = useChatStore((state) => state.loading);
  const { execute } = useQuery();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-4 py-6">
          {messages.length === 0 ? (
            <div className="flex min-h-[65vh] items-center justify-center">
              <div className="max-w-xl rounded-2xl border bg-card/60 p-8 text-center shadow-sm backdrop-blur">
                <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                  <Database className="h-6 w-6 text-primary" />
                </div>
                <h2 className="text-xl font-semibold">Multi-Database AI Query Engine</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Query SQL, MongoDB, Graph, and Vector databases with natural language.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message) =>
                message.role === 'user' ? (
                  <UserMessageBubble key={message.id} content={message.text} timestamp={message.timestamp} />
                ) : (
                  <AssistantMessageBubble
                    key={message.id}
                    content={message.text}
                    timestamp={message.timestamp}
                    result={message.result}
                    error={message.error}
                  />
                )
              )}
              {loading && <LoadingIndicator />}
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="border-t bg-background/90 p-4 backdrop-blur">
        <QueryInput onSubmit={execute} disabled={loading} />
      </div>
    </div>
  );
};

export default ChatWindow;
