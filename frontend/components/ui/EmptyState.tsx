export default function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-border-strong bg-surface-alt px-6 py-10 text-center">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="text-text-faint">
        <rect x="3" y="3" width="18" height="18" rx="4" />
        <path d="M8 12h8" strokeLinecap="round" />
      </svg>
      <p className="text-sm font-medium text-text-soft">{message}</p>
      {hint && <p className="max-w-sm text-xs text-text-faint">{hint}</p>}
    </div>
  );
}
