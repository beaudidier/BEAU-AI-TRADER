export type TourProgress = {
  tour_started_at: string | null;
  current_step: number;
  completed_at: string | null;
  skipped_at: string | null;
  tour_version: number;
};

export type TourStep = {
  id: string;
  title: string;
  target: string;
  fallbackTarget?: string;
  body: string;
};

export const TOUR_VERSION: number;
export const TOUR_EVENT: string;
export const productTourSteps: TourStep[];
export function tourStorageKey(userId: string): string;
export function emptyTourProgress(): TourProgress;
export function readTourProgress(storage: Storage, userId: string, version?: number): TourProgress;
export function writeTourProgress(storage: Storage, userId: string, progress: TourProgress): TourProgress;
export function shouldAutoStart(progress: TourProgress): boolean;
export function startTour(progress: TourProgress, now?: string): TourProgress;
export function restartTour(version?: number, now?: string): TourProgress;
export function moveTour(progress: TourProgress, direction: "back" | "next", total?: number): TourProgress;
export function finishTour(progress: TourProgress, now?: string): TourProgress;
export function skipTour(progress: TourProgress, now?: string): TourProgress;
export function isMobileViewport(width: number): boolean;
export function nextAvailableStep(steps: TourStep[], index: number, isAvailable: (step: TourStep) => boolean): number;
export function keyboardTourAction(key: string): "next" | "back" | "close" | null;
