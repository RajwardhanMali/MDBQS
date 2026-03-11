import React from 'react';
import { formatDateTime } from '../utils/formatters';

interface UserMessageBubbleProps {
  content: string;
  timestamp: number;
}

const UserMessageBubble: React.FC<UserMessageBubbleProps> = ({ content, timestamp }) => {
  return (
    <div className="flex justify-end mb-4">
      <div className="max-w-xs lg:max-w-md xl:max-w-lg">
        <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-md px-4 py-3 shadow-sm">
          <p className="text-sm break-words">{content}</p>
        </div>
        <p className="text-xs text-muted-foreground mt-1 text-right">
          {formatDateTime(timestamp)}
        </p>
      </div>
    </div>
  );
};

export default UserMessageBubble;
