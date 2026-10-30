export default function Loading() {
  return (
    <div className="flex min-h-full flex-col items-center bg-bg px-6 py-10">
      <div className="h-[26px] w-40 animate-pulse rounded bg-surface-sunken" />
      <div className="mt-12 w-full max-w-[640px] animate-pulse space-y-5 rounded-[20px] border border-border bg-surface p-14">
        <div className="h-3 w-32 rounded-full bg-surface-sunken" />
        <div className="h-9 w-80 rounded-lg bg-surface-sunken" />
        <div className="h-16 rounded-xl bg-surface-sunken" />
        <div className="h-16 rounded-xl bg-surface-sunken" />
      </div>
    </div>
  );
}
