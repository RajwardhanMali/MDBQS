import { Columns3, DatabaseZap } from 'lucide-react';
import { SchemaSuggestion } from '../types/apiTypes';
import { cn } from '../utils/cn';

interface SuggestionDropdownProps {
  suggestions: SchemaSuggestion[];
  selectedIndex: number;
  onSelect: (suggestion: SchemaSuggestion) => void;
}

const SuggestionDropdown = ({ suggestions, selectedIndex, onSelect }: SuggestionDropdownProps) => {
  if (!suggestions.length) {
    return null;
  }

  return (
<div className="absolute bottom-full left-0 right-14 z-20 mb-2 max-h-72 overflow-y-auto rounded-3xl border border-border/70 bg-card/80 backdrop-blur-md p-2 shadow-lg">      {suggestions.map((suggestion, index) => (
        <button
          key={suggestion.id}
          type="button"
          onClick={() => onSelect(suggestion)}
          className={cn(
            'flex w-full items-start gap-3 rounded-2xl px-3 py-2 text-left text-sm transition-colors hover:bg-accent',
            index === selectedIndex && 'bg-accent'
          )}
        >
          {suggestion.field ? (
            <Columns3 className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
          ) : (
            <DatabaseZap className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
          )}
          <div className="min-w-0">
            <p className="truncate font-medium text-foreground">{suggestion.text}</p>
            <p className="truncate text-xs text-muted-foreground">
              {[suggestion.source, suggestion.entity, suggestion.field_type].filter(Boolean).join(' | ') || 'Schema result'}
            </p>
          </div>
        </button>
      ))}
    </div>
  );
};

export default SuggestionDropdown;
