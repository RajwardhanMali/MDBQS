import { useCallback } from 'react';
import { useChatStore } from '../store/chatStore';

export const useQuery = () => {
  const submitQuery = useChatStore((state) => state.submitQuery);
  const loading = useChatStore((state) => state.loading);

  const execute = useCallback(
    async (query: string) => {
      await submitQuery(query);
    },
    [submitQuery]
  );

  return {
    execute,
    isSubmitting: loading,
  };
};
