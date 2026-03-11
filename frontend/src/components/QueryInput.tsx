import { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { cn } from '../utils/cn';
import SuggestionDropdown from './SuggestionDropdown';

interface QueryInputProps {
  onSubmit: (query: string) => void | Promise<void>;
  disabled?: boolean;
}

const QueryInput = ({ onSubmit, disabled = false }: QueryInputProps) => {
  const composerDraft = useChatStore((state) => state.composerDraft);
  const setComposerDraft = useChatStore((state) => state.setComposerDraft);
  const suggestions = useChatStore((state) => state.schemaSuggestions);
  const searchSchema = useChatStore((state) => state.searchSchema);
  const clearSchemaSuggestions = useChatStore((state) => state.clearSchemaSuggestions);
  const schemaLoading = useChatStore((state) => state.schemaLoading);

  const [value, setValue] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const showSuggestions = suggestions.length > 0;

  const debouncedFetch = useMemo(() => {
    let timeout: ReturnType<typeof setTimeout> | undefined;
    return (query: string) => {
      if (timeout) {
        clearTimeout(timeout);
      }

      timeout = setTimeout(() => {
        void searchSchema(query);
      }, 250);
    };
  }, [searchSchema]);

  useEffect(() => {
    setValue(composerDraft);
  }, [composerDraft]);

  useEffect(() => {
    const element = inputRef.current;
    if (!element) {
      return;
    }

    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, 180)}px`;
  }, [value]);

  const submit = async () => {
    const query = value.trim();
    if (!query || disabled) {
      return;
    }

    await onSubmit(query);
    setValue('');
    setSelectedIndex(-1);
    setComposerDraft('');
    clearSchemaSuggestions();
  };

  return (
    <div className="relative mx-auto max-w-5xl">
      <div className="mb-2 flex items-center justify-between gap-3 px-1 text-xs text-muted-foreground">
        <span>Ask about any connected source. The reply can contain multiple result sets.</span>
        <span>Ctrl/Cmd + K</span>
      </div>
      <div className="relative flex items-end gap-2">
        <textarea
          ref={inputRef}
          data-query-input="true"
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(event) => {
            const next = event.target.value;
            setValue(next);
            setComposerDraft(next);
            setSelectedIndex(-1);
            debouncedFetch(next);
          }}
          onKeyDown={async (event) => {
            if (event.key === 'ArrowDown' && showSuggestions) {
              event.preventDefault();
              setSelectedIndex((prev) => Math.min(prev + 1, suggestions.length - 1));
              return;
            }

            if (event.key === 'ArrowUp' && showSuggestions) {
              event.preventDefault();
              setSelectedIndex((prev) => Math.max(prev - 1, -1));
              return;
            }

            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              if (showSuggestions && selectedIndex >= 0) {
                const suggestion = suggestions[selectedIndex];
                setValue(suggestion.text);
                setComposerDraft(suggestion.text);
                clearSchemaSuggestions();
                return;
              }
              await submit();
            }

            if (event.key === 'Escape') {
              clearSchemaSuggestions();
              setSelectedIndex(-1);
            }
          }}
          placeholder="Ask a question about your connected data sources..."
          className={cn(
            'w-full resize-none rounded-[1.75rem] border border-border/70 bg-card/80 px-4 py-3 pr-14 text-sm shadow-sm backdrop-blur',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            disabled && 'opacity-70'
          )}
        />

        <button
          type="button"
          disabled={disabled || !value.trim()}
          onClick={() => void submit()}
          className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>

        {schemaLoading && (
          <div className="absolute right-16 top-3 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
          </div>
        )}
      </div>

      {showSuggestions && (
        <SuggestionDropdown
          suggestions={suggestions}
          selectedIndex={selectedIndex}
          onSelect={(suggestion) => {
            setValue(suggestion.text);
            setComposerDraft(suggestion.text);
            clearSchemaSuggestions();
            setSelectedIndex(-1);
            inputRef.current?.focus();
          }}
        />
      )}
    </div>
  );
};

export default QueryInput;
