import { Columns, Table2 } from 'lucide-react';
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
    <div className="absolute bottom-full left-0 right-14 z-20 mb-2 max-h-64 overflow-y-auto rounded-xl border bg-popover shadow-lg">
      {suggestions.map((suggestion, index) => (
        <button
          key={`${suggestion.text}-${index}`}
          type="button"
          onClick={() => onSelect(suggestion)}
          className={cn(
            'flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-accent',
            index === selectedIndex && 'bg-accent'
          )}
        >
          {suggestion.field ? <Columns className="h-4 w-4 text-muted-foreground" /> : <Table2 className="h-4 w-4 text-muted-foreground" />}
          <div className="min-w-0">
            <p className="truncate font-medium">{suggestion.text}</p>
            <p className="truncate text-xs text-muted-foreground">{suggestion.source ?? 'Schema result'}</p>
          </div>
        </button>
      ))}
    </div>
  );
};

export default SuggestionDropdown;
