import { educationTerms } from "../services/beginnerMode";

export type EducationTerm = keyof typeof educationTerms;

export default function BeginnerTerm({ term, children }: { term: EducationTerm; children?: React.ReactNode }) {
  const explanation = educationTerms[term];
  return <span className="group relative inline-flex">
    <button type="button" className="cursor-help rounded-sm text-left underline decoration-dotted underline-offset-4 outline-none focus-visible:ring-2 focus-visible:ring-cyan-300" aria-describedby={`term-${term.replaceAll(" ", "-")}`}>{children ?? term}</button>
    <span id={`term-${term.replaceAll(" ", "-")}`} role="tooltip" className="pointer-events-none absolute bottom-full left-0 z-30 mb-2 hidden w-64 rounded-lg border border-slate-600 bg-slate-900 p-3 text-xs font-normal leading-5 text-slate-100 shadow-xl group-hover:block group-focus-within:block">{explanation}</span>
  </span>;
}
