import { Link } from "react-router-dom";

import Header from "../components/Header";
import Sidebar, { type AppPage } from "../components/Sidebar";

type BetaGuidePageProps = {
  onNavigate: (page: AppPage) => void;
};

const steps = [
  ["1", "Dashboard", "Start with the ranked opportunities and market briefing.", "/dashboard"],
  ["2", "Latest Signals", "Inspect every validated replay setup, its status, risk, and evidence.", "/latest-signals"],
  ["3", "Trade Workspace", "Open a ticker to review the chart, institutional analysis, and frozen trade plan.", "/latest-signals"],
  ["4", "Paper Trade", "Confirm the proposed size and risk. Portfolio limits are enforced automatically.", "/paper-trading"],
  ["5", "Evidence", "Challenge the methodology using wins, losses, expiries, and rejected examples.", "/evidence"],
  ["6", "Forward Validation", "Monitor new signals, runner health, sample progress, and paper outcomes.", "/forward-validation"],
  ["7", "Feedback", "Submit structured feedback and complete a professional review for each signal.", "/feedback"],
];

export default function BetaGuidePage({ onNavigate }: BetaGuidePageProps) {
  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 lg:flex">
      <Sidebar activePage="beta-guide" onNavigate={onNavigate} />
      <div className="min-w-0 flex-1">
        <Header eyebrow="Professional trader private beta" title="Tester Onboarding" />
        <main className="mx-auto max-w-6xl space-y-6 p-5 sm:p-8">
          <section className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-6">
            <p className="text-sm font-semibold text-cyan-200">Your review objective</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Assess decision quality, execution logic, and operational trust</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              Follow the workflow below, challenge every setup as you would in a professional process, and record missing context. Historical examples are retrospective evidence, not guaranteed future performance.
            </p>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            {steps.map(([number, title, description, href]) => (
              <article key={number} className="flex gap-4 rounded-xl border border-slate-800 bg-slate-900/50 p-5">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-cyan-400/10 text-sm font-semibold text-cyan-200">{number}</span>
                <div>
                  <h3 className="font-semibold text-white">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
                  <Link to={href} className="mt-3 inline-flex text-sm font-semibold text-cyan-300 transition hover:text-cyan-200">Open {title} →</Link>
                </div>
              </article>
            ))}
          </section>

          <section className="rounded-xl border border-amber-300/20 bg-amber-300/10 p-5 text-sm leading-6 text-amber-100">
            Use paper trading only. Stops and targets are reference levels, forward validation is incomplete, and no screen in this application authorizes live-money execution.
          </section>
        </main>
      </div>
    </div>
  );
}
