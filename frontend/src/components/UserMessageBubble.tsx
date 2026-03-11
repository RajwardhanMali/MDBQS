import { ChatMessage } from '../types/apiTypes';
import { formatDateTime } from '../utils/formatters';

interface UserMessageBubbleProps {
  message: ChatMessage;
}

const UserMessageBubble = ({ message }: UserMessageBubbleProps) => {
  return (
    <div className="flex justify-end">
      <div className="max-w-2xl">
        <div className="rounded-[1.5rem] rounded-tr-md bg-primary px-4 py-3 text-sm text-primary-foreground shadow-sm">
          <p className="break-words leading-6">{message.content}</p>
        </div>
        <p className="mt-1 text-right text-xs text-muted-foreground">{formatDateTime(message.created_at)}</p>
      </div>
    </div>
  );
};

export default UserMessageBubble;
