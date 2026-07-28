import assert from "node:assert/strict";
import test from "node:test";

import {
  emptyTourProgress,
  finishTour,
  moveTour,
  readTourProgress,
  restartTour,
  shouldAutoStart,
  skipTour,
  startTour,
  TOUR_VERSION,
  tourStorageKey,
  writeTourProgress,
} from "../src/tour/productTour.js";

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

test("first successful login starts the tour", () => {
  const store = storage();
  const progress = readTourProgress(store, "user-a");
  assert.equal(shouldAutoStart(progress), true);
  assert.equal(startTour(progress, "start").tour_started_at, "start");
});

test("second login does not restart a completed tour", () => {
  const store = storage();
  writeTourProgress(store, "user-a", finishTour(startTour(emptyTourProgress(), "start"), "done"));
  assert.equal(shouldAutoStart(readTourProgress(store, "user-a")), false);
});

test("skip is final by default", () => {
  assert.equal(shouldAutoStart(skipTour(startTour(emptyTourProgress(), "start"), "skip")), false);
});

test("progress resumes and supports back/next", () => {
  const store = storage();
  const moved = moveTour(moveTour(startTour(emptyTourProgress(), "start"), "next"), "next");
  writeTourProgress(store, "user-a", moved);
  assert.equal(readTourProgress(store, "user-a").current_step, 2);
  assert.equal(moveTour(moved, "back").current_step, 1);
});

test("version change resets completion for a major update", () => {
  const store = storage();
  writeTourProgress(store, "user-a", finishTour(emptyTourProgress(), "done"));
  const reset = readTourProgress(store, "user-a", TOUR_VERSION + 1);
  assert.equal(reset.completed_at, null);
  assert.equal(shouldAutoStart(reset), true);
});

test("tour progress is isolated per user", () => {
  const store = storage();
  writeTourProgress(store, "user-a", finishTour(emptyTourProgress(), "done"));
  assert.notEqual(tourStorageKey("user-a"), tourStorageKey("user-b"));
  assert.equal(readTourProgress(store, "user-b").completed_at, null);
});

test("manual restart clears completed and skipped timestamps", () => {
  const restarted = restartTour(TOUR_VERSION, "again");
  assert.equal(restarted.tour_started_at, "again");
  assert.equal(restarted.completed_at, null);
  assert.equal(restarted.skipped_at, null);
  assert.equal(restarted.current_step, 0);
});
