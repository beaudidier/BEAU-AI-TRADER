import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  isMobileViewport,
  keyboardTourAction,
  nextAvailableStep,
  productTourSteps,
} from "../src/tour/productTour.js";

test("unavailable or hidden targets are skipped safely", () => {
  const steps = [{ id: "missing" }, { id: "visible" }, { id: "later" }];
  assert.equal(nextAvailableStep(steps, 0, (step) => step.id === "visible"), 1);
  assert.equal(nextAvailableStep(steps, 2, () => false), -1);
});

test("390px uses mobile tour placement", () => {
  assert.equal(isMobileViewport(390), true);
  assert.equal(isMobileViewport(640), false);
});

test("keyboard navigation maps next, back, and safe close", () => {
  assert.equal(keyboardTourAction("ArrowRight"), "next");
  assert.equal(keyboardTourAction("Enter"), "next");
  assert.equal(keyboardTourAction("ArrowLeft"), "back");
  assert.equal(keyboardTourAction("Escape"), "close");
  assert.equal(keyboardTourAction("Tab"), null);
});

test("final tour contains 14 focused steps with real targets", () => {
  assert.deepEqual(productTourSteps.map((step) => step.id), [
    "dashboard", "best-setup", "status", "current-price", "entry", "stop",
    "profit-targets", "maximum-loss", "next-action", "paper-risk",
    "historical-evidence", "forward-validation", "feedback", "mode-switch",
  ]);
  assert.equal(productTourSteps.length, 14);
  assert.equal(productTourSteps.some((step) => step.id === "portfolio-journal"), false);
});

test("safety wording is explicit in the tour copy", () => {
  const copy = productTourSteps.map((step) => step.body).join(" ");
  for (const phrase of [
    "does not mean buy now",
    "Confidence is a rules-based score, not a guaranteed probability",
    "no real money",
    "Neither target is guaranteed",
    "expire or become invalid",
  ]) assert.match(copy, new RegExp(phrase));
});

test("dialog implementation includes focus, accessibility, scrolling, and mobile target contracts", () => {
  const source = readFileSync(new URL("../src/components/ProductTour.tsx", import.meta.url), "utf8");
  for (const contract of [
    'role="dialog"',
    'aria-modal="true"',
    'aria-labelledby="product-tour-title"',
    'aria-describedby="product-tour-description"',
    'event.key === "Tab"',
    'scrollIntoView',
    '"fixed inset-x-3 bottom-3"',
    "min-h-11",
  ]) assert.equal(source.includes(contract), true, `missing ${contract}`);
});
