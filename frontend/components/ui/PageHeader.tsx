export default function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-6 animate-reveal">
      <div>
        <h1 className="font-display font-medium italic text-[28px] leading-tight text-text md:text-[32px]">
          {title}
        </h1>
        {description && <p className="mt-2.5 max-w-2xl text-[14.5px] text-text-soft">{description}</p>}
      </div>
      {action}
    </div>
  );
}
