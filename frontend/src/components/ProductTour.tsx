import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { useAuth } from "../hooks/useAuth";
import {
  finishTour,
  keyboardTourAction,
  moveTour,
  nextAvailableStep,
  productTourSteps,
  readTourProgress,
  restartTour,
  shouldAutoStart,
  skipTour,
  startTour,
  TOUR_EVENT,
  writeTourProgress,
} from "../tour/productTour";

type TargetBox = { top: number; left: number; width: number; height: number };

export default function ProductTour() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [target, setTarget] = useState<TargetBox | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const userId = user?.id;

  const persist = useCallback((update: (progress: ReturnType<typeof readTourProgress>) => ReturnType<typeof readTourProgress>) => {
    if (!userId) return;
    const current = readTourProgress(window.localStorage, userId);
    const next = update(current);
    writeTourProgress(window.localStorage, userId, next);
    setStepIndex(next.current_step);
  }, [userId]);

  useEffect(() => {
    if (!userId) { setOpen(false); return; }
    const progress = readTourProgress(window.localStorage, userId);
    if (shouldAutoStart(progress)) {
      const started = startTour(progress);
      writeTourProgress(window.localStorage, userId, started);
      setStepIndex(started.current_step);
      setOpen(true);
    }
  }, [userId]);

  useEffect(() => {
    const restart = () => {
      if (!userId) return;
      const progress = restartTour();
      writeTourProgress(window.localStorage, userId, progress);
      setStepIndex(0);
      setOpen(true);
    };
    window.addEventListener(TOUR_EVENT, restart);
    return () => window.removeEventListener(TOUR_EVENT, restart);
  }, [userId]);

  const locate = useCallback(() => {
    if (!open) return;
    const availableIndex = nextAvailableStep(productTourSteps, stepIndex, (step) => {
      const candidate = document.querySelector(step.target) ?? (step.fallbackTarget ? document.querySelector(step.fallbackTarget) : null);
      if (!(candidate instanceof HTMLElement)) return false;
      const style = window.getComputedStyle(candidate);
      return style.display !== "none" && style.visibility !== "hidden" && candidate.getClientRects().length > 0;
    });
    if (availableIndex < 0) {
      persist((progress) => finishTour(progress));
      setOpen(false);
      return;
    }
    if (availableIndex !== stepIndex) {
      persist((progress) => ({ ...progress, current_step: availableIndex }));
      return;
    }
    const step = productTourSteps[availableIndex];
    const element = (document.querySelector(step.target) ?? (step.fallbackTarget ? document.querySelector(step.fallbackTarget) : null)) as HTMLElement;
    element.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    window.setTimeout(() => {
      const rect = element.getBoundingClientRect();
      setTarget({ top: Math.max(8, rect.top - 6), left: Math.max(8, rect.left - 6), width: rect.width + 12, height: rect.height + 12 });
    }, 180);
  }, [open, persist, stepIndex]);

  useLayoutEffect(locate, [locate]);
  useEffect(() => {
    if (!open) return undefined;
    const update = () => locate();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => { window.removeEventListener("resize", update); window.removeEventListener("scroll", update, true); };
  }, [locate, open]);

  const closeSafely = useCallback(() => setOpen(false), []);
  const back = useCallback(() => persist((progress) => moveTour(progress, "back")), [persist]);
  const next = useCallback(() => {
    if (stepIndex === productTourSteps.length - 1) {
      persist((progress) => finishTour(progress));
      setOpen(false);
    } else {
      persist((progress) => moveTour(progress, "next"));
    }
  }, [persist, stepIndex]);
  const skip = useCallback(() => {
    persist((progress) => skipTour(progress));
    setOpen(false);
  }, [persist]);

  useEffect(() => {
    if (!open) return undefined;
    const previousFocus = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      const action = keyboardTourAction(event.key);
      if (action) {
        event.preventDefault();
        if (action === "next") next();
        if (action === "back") back();
        if (action === "close") closeSafely();
        return;
      }
      if (event.key === "Tab" && dialogRef.current) {
        const controls = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled])")];
        if (!controls.length) return;
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => { document.removeEventListener("keydown", onKeyDown); previousFocus?.focus(); };
  }, [back, closeSafely, next, open]);

  if (!open || !userId) return null;
  const step = productTourSteps[stepIndex];
  const mobile = window.innerWidth < 640;
  const desktopPosition = (() => {
    if (!target) return { top: 24, left: 24 };
    const gap = 14;
    const dialogWidth = 368;
    const dialogHeight = 310;
    const clampTop = (value: number) => Math.min(window.innerHeight - dialogHeight - 16, Math.max(16, value));
    const clampLeft = (value: number) => Math.min(window.innerWidth - dialogWidth - 16, Math.max(16, value));
    if (target.left + target.width + gap + dialogWidth <= window.innerWidth) {
      return { top: clampTop(target.top), left: target.left + target.width + gap };
    }
    if (target.left - gap - dialogWidth >= 0) {
      return { top: clampTop(target.top), left: target.left - gap - dialogWidth };
    }
    if (target.top + target.height + gap + dialogHeight <= window.innerHeight) {
      return { top: target.top + target.height + gap, left: clampLeft(target.left) };
    }
    return { top: Math.max(16, target.top - dialogHeight - gap), left: clampLeft(target.left) };
  })();
  const dialogStyle = mobile
    ? undefined
    : desktopPosition;

  return (
    <div className="fixed inset-0 z-[100]" aria-live="polite">
      {target ? <>
        <div className="fixed left-0 right-0 top-0 bg-slate-950/85" style={{ height: target.top }} />
        <div className="fixed bottom-0 left-0 bg-slate-950/85" style={{ top: target.top, width: target.left }} />
        <div className="fixed bottom-0 right-0 bg-slate-950/85" style={{ top: target.top, left: target.left + target.width }} />
        <div className="fixed bottom-0 bg-slate-950/85" style={{ top: target.top + target.height, left: target.left, width: target.width }} />
        <div className="pointer-events-none fixed rounded-xl border-2 border-cyan-300 shadow-[0_0_0_4px_rgba(34,211,238,0.25)]" style={target} aria-hidden="true" />
      </> : <div className="fixed inset-0 bg-slate-950/85" />}
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="product-tour-title" aria-describedby="product-tour-description" tabIndex={-1} style={dialogStyle} className={`${mobile ? "fixed inset-x-3 bottom-3" : "fixed w-[23rem]"} rounded-2xl border border-cyan-300/50 bg-slate-900 p-5 text-slate-100 shadow-2xl outline-none`}>
        <div className="flex items-center justify-between gap-3"><p className="text-xs font-bold uppercase tracking-wider text-cyan-300">Step {stepIndex + 1} of {productTourSteps.length}</p><button type="button" onClick={closeSafely} aria-label="Close tour and resume later" className="grid min-h-11 min-w-11 place-items-center rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white">×</button></div>
        <h2 id="product-tour-title" className="mt-2 text-xl font-semibold text-white">{step.title}</h2>
        <p id="product-tour-description" className="mt-2 text-sm leading-6 text-slate-300">{step.body}</p>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <button type="button" onClick={back} disabled={stepIndex === 0} className="min-h-11 rounded-lg border border-slate-600 px-4 text-sm font-semibold disabled:opacity-40">Back</button>
          <button type="button" onClick={next} className="min-h-11 flex-1 rounded-lg bg-cyan-300 px-4 text-sm font-bold text-slate-950 hover:bg-cyan-200">{stepIndex === productTourSteps.length - 1 ? "Finish" : "Next"}</button>
          <button type="button" onClick={skip} className="min-h-11 rounded-lg px-3 text-sm font-semibold text-slate-300 hover:bg-slate-800">Skip tour</button>
        </div>
        <p className="mt-3 text-xs text-slate-500">Keyboard: ← Back · → or Enter Next · Esc close and resume later</p>
      </div>
    </div>
  );
}
