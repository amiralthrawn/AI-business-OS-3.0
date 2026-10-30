export type BadgeTone = "danger" | "warning" | "success" | "accent" | "neutral";

const TONE_CLASSES: Record<BadgeTone, string> = {
  danger: "bg-danger-soft text-danger",
  warning: "bg-warning-soft text-warning",
  success: "bg-success-soft text-success",
  accent: "bg-accent-soft text-accent-strong",
  neutral: "bg-surface-sunken text-text-soft",
};

export default function Badge({
  label,
  tone = "neutral",
  icon,
}: {
  label: string;
  tone?: BadgeTone;
  icon?: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap ${TONE_CLASSES[tone]}`}
    >
      {icon}
      {label}
    </span>
  );
}
