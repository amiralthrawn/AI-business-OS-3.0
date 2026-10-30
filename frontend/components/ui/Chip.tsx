"use client";

export default function Chip({
  label,
  selected,
  onClick,
  icon,
}: {
  label: string;
  selected: boolean;
  onClick?: () => void;
  icon?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`flex items-center gap-2 rounded-xl border-[1.5px] px-3.5 py-2.5 text-[13.5px] font-medium transition-colors ${
        selected
          ? "border-accent bg-accent-soft text-accent-strong font-semibold"
          : "border-border-strong text-text-soft hover:border-text-faint"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
