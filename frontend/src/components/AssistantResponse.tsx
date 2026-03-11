import { ChatMessage } from '../types/apiTypes';
import ResultSetRenderer from './ResultSetRenderer';
import TraceViewer from './TraceViewer';

interface AssistantResponseProps {
  message: ChatMessage;
}

const AssistantResponse = ({ message }: AssistantResponseProps) => {
  const payload = message.answer_payload;
  if (!payload) {
    return null;
  }

  return (
    <div className="mt-3 space-y-4">
      {payload.result_sets.length > 0 ? (
        payload.result_sets.map((resultSet) => <ResultSetRenderer key={`${message.message_id}-${resultSet.key}`} resultSet={resultSet} />)
      ) : (
        <div className="rounded-2xl border border-border/70 bg-card/70 px-4 py-3 text-sm text-muted-foreground">
          {payload.trace.errors.length > 0 ? 'The assistant returned no result sets because the request failed.' : 'No matching data was returned.'}
        </div>
      )}

      {(payload.citations.length > 0 || payload.explain.length > 0) && (
        <div className="rounded-2xl border border-border/70 bg-card/70 p-4 shadow-sm">
          {payload.citations.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">Citations</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {payload.citations.map((citation) => (
                  <span
                    key={`${citation.server_id}-${citation.tool_name}-${citation.key}`}
                    className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs text-muted-foreground"
                  >
                    {citation.server_id} via {citation.tool_name} ({citation.count} rows)
                  </span>
                ))}
              </div>
            </div>
          )}

          {payload.explain.length > 0 && (
            <details className="mt-4 rounded-2xl border border-border/70 bg-background/60 px-4 py-3" open>
              <summary className="cursor-pointer text-sm font-medium text-foreground">How this was answered</summary>
              <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                {payload.explain.map((line, index) => (
                  <li key={`${message.message_id}-explain-${index}`}>{line}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      <TraceViewer messageId={message.message_id} initialTrace={payload.trace} />
    </div>
  );
};

export default AssistantResponse;
