import { QueryResponse } from '../types/apiTypes';
import { formatDateTime } from '../utils/formatters';
import AssistantResponse from './AssistantResponse';

interface AssistantMessageBubbleProps {
  content: string;
  timestamp: number;
  result?: QueryResponse;
  error?: string;
}

const AssistantMessageBubble = ({ content, timestamp, result, error }: AssistantMessageBubbleProps) => {
  return (
    <div className="mb-4 flex justify-start">
      <div className="w-full max-w-5xl">
        <div className="rounded-2xl rounded-tl-md border bg-card px-4 py-3 shadow-sm">
          {error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : (
            <p className="text-sm text-foreground">{content}</p>
          )}
        </div>

        <p className="ml-2 mt-1 text-xs text-muted-foreground">{formatDateTime(timestamp)}</p>

        {result && <AssistantResponse result={result} />}
      </div>
    </div>
  );
};

export default AssistantMessageBubble;
