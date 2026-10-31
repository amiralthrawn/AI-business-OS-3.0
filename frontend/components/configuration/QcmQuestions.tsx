"use client";

import type { QcmQuestion } from "@/lib/types-config";

// Tick-the-boxes questions: the AI gets clear, comparable answers instead of
// vague free text. The free precision under each question is optional.
export default function QcmQuestions({
  questions,
  answers,
  notes,
  onAnswers,
  onNotes,
}: {
  questions: QcmQuestion[];
  answers: Record<string, string[]>;
  notes: Record<string, string>;
  onAnswers: (next: Record<string, string[]>) => void;
  onNotes: (next: Record<string, string>) => void;
}) {
  function toggle(key: string, choice: string) {
    const current = answers[key] ?? [];
    onAnswers({ ...answers, [key]: current.includes(choice) ? current.filter((c) => c !== choice) : [...current, choice] });
  }

  return (
    <div className="space-y-9">
      {questions.map((q) => (
        <fieldset key={q.key}>
          <legend className="text-[15px] font-semibold text-text">{q.title}</legend>
          <p className="mt-0.5 text-[12.5px] text-text-faint">{q.hint}</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {q.choices.map((choice) => {
              const on = (answers[q.key] ?? []).includes(choice);
              return (
                <button
                  key={choice}
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  onClick={() => toggle(q.key, choice)}
                  className={`flex items-start gap-2.5 rounded-xl border-[1.5px] px-3.5 py-3 text-left text-[13.5px] transition-colors ${
                    on ? "border-accent bg-accent-soft font-semibold text-accent-strong" : "border-border-strong text-text-soft hover:border-text-faint"
                  }`}
                >
                  <span className={`mt-0.5 flex h-[17px] w-[17px] shrink-0 items-center justify-center rounded-[5px] border-[1.5px] ${on ? "border-accent bg-accent text-white" : "border-border-strong"}`}>
                    {on && (
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </span>
                  {choice}
                </button>
              );
            })}
          </div>
          <details className="mt-2.5" open={!!notes[q.key]}>
            <summary className="cursor-pointer select-none text-[12.5px] font-medium text-text-soft hover:text-text">Préciser avec vos mots (facultatif)</summary>
            <textarea
              value={notes[q.key] ?? ""}
              onChange={(e) => onNotes({ ...notes, [q.key]: e.target.value })}
              rows={2}
              aria-label={`Précisions : ${q.title}`}
              className="mt-2 w-full resize-none rounded-xl border-[1.5px] border-border-strong px-4 py-3 text-[13.5px] outline-none focus:border-accent"
            />
          </details>
        </fieldset>
      ))}
    </div>
  );
}
