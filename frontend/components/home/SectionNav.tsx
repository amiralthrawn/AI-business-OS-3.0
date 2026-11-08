"use client";

// Jump to a part of the home page without scrolling for it.
export default function SectionNav({ items }: { items: { id: string; label: string }[] }) {
  return (
    <nav className="sticky top-0 z-30 -mx-4 flex gap-2 overflow-x-auto bg-bg/90 px-4 py-2 backdrop-blur sm:-mx-6 sm:px-6 md:-mx-10 md:px-10" aria-label="Sections de l'accueil">
      {items.map((i) => (
        <button
          key={i.id}
          type="button"
          onClick={() => document.getElementById(i.id)?.scrollIntoView({ behavior: "smooth", block: "start" })}
          className="shrink-0 rounded-full border border-border bg-surface px-3.5 py-1.5 text-[12.5px] font-semibold text-text-soft hover:border-accent hover:text-accent-strong"
        >
          {i.label}
        </button>
      ))}
    </nav>
  );
}
