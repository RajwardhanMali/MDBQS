interface ExplainChipsProps {
  chips: string[];
}

const ExplainChips = ({ chips }: ExplainChipsProps) => {
  if (!chips.length) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((chip, index) => (
        <span key={`${chip}-${index}`} className="rounded-full border bg-muted px-2 py-1 text-xs">
          {chip}
        </span>
      ))}
    </div>
  );
};

export default ExplainChips;
