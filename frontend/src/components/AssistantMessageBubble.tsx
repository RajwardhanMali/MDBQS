import { ChatMessage } from '../types/apiTypes';
import { formatDateTime } from '../utils/formatters';
import AssistantResponse from './AssistantResponse';

interface AssistantMessageBubbleProps {
  message: ChatMessage;
}

const AssistantMessageBubble = ({ message }: AssistantMessageBubbleProps) => {
  const answer = message.answer_payload?.answer || message.content;

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-5xl">
        <div className="rounded-[1.75rem] rounded-tl-md border border-border/70 bg-card/90 px-4 py-3 shadow-sm">
          <p className="text-sm leading-6 text-foreground">{answer || 'No answer text returned.'}</p>
        </div>
        <p className="ml-2 mt-1 text-xs text-muted-foreground">{formatDateTime(message.created_at)}</p>
        {message.answer_payload && <AssistantResponse message={message} />}
      </div>
    </div>
  );
};

export default AssistantMessageBubble;
