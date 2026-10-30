export default function Card({
  children,
  className = "",
  as: As = "div",
}: {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "li";
}) {
  return (
    <As className={`rounded-2xl border border-border bg-surface shadow-card ${className}`}>{children}</As>
  );
}
