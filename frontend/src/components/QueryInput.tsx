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
  const [value, setValue] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  const suggestions = useChatStore((state) => state.suggestions);
  const fetchSuggestions = useChatStore((state) => state.fetchSuggestions);
  const clearSuggestions = useChatStore((state) => state.clearSuggestions);

  const inputRef = useRef<HTMLTextAreaElement>(null);

  const showSuggestions = suggestions.length > 0;

  const debouncedFetch = useMemo(() => {
    let timeout: ReturnType<typeof setTimeout> | undefined;
    return (query: string) => {
      if (timeout) {
        clearTimeout(timeout);
      }

      timeout = setTimeout(async () => {
        if (query.trim().length < 2) {
          clearSuggestions();
          return;
        }
        setLoadingSuggestions(true);
        await fetchSuggestions(query);
        setLoadingSuggestions(false);
      }, 250);
    };
  }, [clearSuggestions, fetchSuggestions]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) {
      return;
    }
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [value]);

  const submit = async () => {
    const query = value.trim();
    if (!query || disabled) {
      return;
    }

    await onSubmit(query);
    setValue('');
    setSelectedIndex(-1);
    clearSuggestions();
  };

  return (
    <div className="relative mx-auto max-w-5xl">
      <div className="relative flex items-end gap-2">
        <textarea
          ref={inputRef}
          data-query-input="true"
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(e) => {
            const next = e.target.value;
            setValue(next);
            setSelectedIndex(-1);
            debouncedFetch(next);
          }}
          onKeyDown={async (e) => {
            if (e.key === 'ArrowDown' && showSuggestions) {
              e.preventDefault();
              setSelectedIndex((prev) => Math.min(prev + 1, suggestions.length - 1));
              return;
            }

            if (e.key === 'ArrowUp' && showSuggestions) {
              e.preventDefault();
              setSelectedIndex((prev) => Math.max(prev - 1, -1));
              return;
            }

            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (showSuggestions && selectedIndex >= 0) {
                setValue(suggestions[selectedIndex].text);
                clearSuggestions();
                return;
              }
              await submit();
            }

            if (e.key === 'Escape') {
              clearSuggestions();
              setSelectedIndex(-1);
            }
          }}
          placeholder="Ask a question about your data..."
          className={cn(
            'w-full resize-none rounded-2xl border bg-card/70 px-4 py-3 pr-12 text-sm shadow-sm backdrop-blur',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            disabled && 'opacity-70'
          )}
        />

        <button
          type="button"
          disabled={disabled || !value.trim()}
          onClick={submit}
          className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>

        {loadingSuggestions && (
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
            clearSuggestions();
            setSelectedIndex(-1);
            inputRef.current?.focus();
          }}
        />
      )}
    </div>
  );
};

export default QueryInput;
