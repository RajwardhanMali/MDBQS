import { Bot } from 'lucide-react';

interface LoadingIndicatorProps {
  label?: string;
}

export default function LoadingIndicator({ label = 'Working across connected sources' }: LoadingIndicatorProps) {
  return (
    <div className="flex max-w-4xl items-start gap-3">
      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
        <Bot className="h-4 w-4 text-primary" />
      </div>
      <div className="rounded-2xl rounded-tl-md bg-muted px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/60" />
            <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '0.1s' }} />
            <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '0.2s' }} />
          </div>
          <span className="text-xs text-muted-foreground">{label}</span>
        </div>
      </div>
    </div>
  );
}
