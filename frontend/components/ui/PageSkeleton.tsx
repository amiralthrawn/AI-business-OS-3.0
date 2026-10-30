export default function PageSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <main className="p-10 md:p-12">
      <div className="animate-pulse space-y-10">
        <div className="space-y-3">
          <div className="h-3 w-32 rounded-full bg-surface-sunken" />
          <div className="h-8 w-64 rounded-lg bg-surface-sunken" />
          <div className="h-4 w-96 rounded-full bg-surface-sunken" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} className="h-20 rounded-2xl border border-border bg-surface-alt" />
          ))}
        </div>
      </div>
    </main>
  );
}
