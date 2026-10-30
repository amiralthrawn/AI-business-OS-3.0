import InlineSpinner from "@/components/ui/InlineSpinner";

type Variant = "primary" | "ghost" | "danger-ghost";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-text text-surface hover:bg-text/90",
  ghost: "border-[1.5px] border-border-strong text-text hover:border-text-faint",
  "danger-ghost": "border-[1.5px] border-danger-soft text-danger hover:border-danger/40",
};

export default function Button({
  children,
  variant = "primary",
  loading = false,
  className = "",
  ...props
}: {
  children: React.ReactNode;
  variant?: Variant;
  loading?: boolean;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-[13.5px] font-semibold transition-colors disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {loading && <InlineSpinner />}
      {children}
    </button>
  );
}
