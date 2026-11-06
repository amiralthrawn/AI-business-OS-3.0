import Link from "next/link";

export const PAGE_SIZE = 50;

// A real company has thousands of customers, contacts or references: lists are
// shown one page at a time, with a search box, so the page stays fast.
export function paginate<T>(items: T[], page: number, size = PAGE_SIZE): T[] {
  return items.slice((page - 1) * size, page * size);
}

export function matches(q: string, ...fields: (string | null | undefined)[]): boolean {
  const needle = q.trim().toLowerCase();
  return !needle || fields.some((f) => (f ?? "").toLowerCase().includes(needle));
}

export function pageOf(raw: string | undefined): number {
  const n = Number.parseInt(raw ?? "1", 10);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

// `params` = the page's other query parameters (tab...) so the search and the
// page links keep the person where they are.
export default function ListPager({
  basePath,
  params,
  q,
  page,
  total,
  size = PAGE_SIZE,
  placeholder = "Rechercher…",
  pageKey = "p",
}: {
  basePath: string;
  params: Record<string, string | undefined>;
  q: string;
  page: number;
  total: number;
  size?: number;
  placeholder?: string;
  pageKey?: string;
}) {
  const link = (p: number) => {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) sp.set(k, v);
    if (q) sp.set("q", q);
    if (p > 1) sp.set(pageKey, String(p));
    const s = sp.toString();
    return s ? `${basePath}?${s}` : basePath;
  };
  const pages = Math.max(1, Math.ceil(total / size));
  const from = total === 0 ? 0 : (page - 1) * size + 1;
  const to = Math.min(total, page * size);

  return (
    <div className="space-y-3">
      <form action={basePath} method="get" className="flex gap-2">
        {Object.entries(params).map(([k, v]) => (v ? <input key={k} type="hidden" name={k} value={v} /> : null))}
        <input
          name="q"
          defaultValue={q}
          placeholder={placeholder}
          className="min-w-0 flex-1 rounded-xl border-[1.5px] border-border-strong bg-surface px-4 py-2.5 text-[13.5px] outline-none focus:border-accent"
        />
        <button type="submit" className="rounded-xl border-[1.5px] border-border-strong px-4 py-2.5 text-[13px] font-semibold text-text hover:border-accent">
          Chercher
        </button>
        {q && (
          <Link href={link(1).replace(/[?&]q=[^&]*/, "").replace("?&", "?")} className="flex items-center px-2 text-[12.5px] text-text-soft hover:underline">
            Effacer
          </Link>
        )}
      </form>
      <div className="flex items-center justify-between gap-3 text-[12.5px] text-text-soft">
        <span>
          {total === 0 ? "Aucun résultat" : `${from}–${to} sur ${new Intl.NumberFormat("fr-FR").format(total)}`}
        </span>
        {pages > 1 && (
          <span className="flex items-center gap-2">
            {page > 1 && <Link href={link(page - 1)} className="rounded-lg border border-border-strong px-3 py-1.5 font-semibold text-text hover:border-accent">← Précédent</Link>}
            {page < pages && <Link href={link(page + 1)} className="rounded-lg border border-border-strong px-3 py-1.5 font-semibold text-text hover:border-accent">Suivant →</Link>}
          </span>
        )}
      </div>
    </div>
  );
}
