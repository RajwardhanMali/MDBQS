import { useCallback } from 'react';
import { useChatStore } from '../store/chatStore';

export const useQuery = () => {
  const sendMessage = useChatStore((state) => state.sendMessage);
  const loading = useChatStore((state) => state.sendingMessage);

  const execute = useCallback(
    async (query: string) => {
      await sendMessage(query);
    },
    [sendMessage]
  );

  return {
    execute,
    isSubmitting: loading,
  };
};
