import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { isStalePrice, setupPresentation } from "../src/services/setupPresentation.js";

test("waiting setup says wait, not buy", () => {
  assert.deepEqual(setupPresentation("waiting_for_entry", 106.55), {
    label: "Waiting for entry",
    tone: "amber",
    action: "Wait for $106.55",
  });
});

test("entry-triggered setup is ready for paper trade", () => {
  assert.equal(setupPresentation("entry_triggered", 100).label, "Ready for paper trade");
});

test("invalidated and portfolio-limited setups are blocked", () => {
  assert.equal(setupPresentation("invalidated", 100).label, "Blocked");
  assert.match(setupPresentation("waiting_for_entry", 100, { portfolioBlocked: true }).action, /risk limit/i);
});

test("expired setup cannot be acted on", () => {
  assert.equal(setupPresentation("expired", 100).label, "Expired");
});

test("stale data overrides an otherwise valid setup", () => {
  assert.equal(setupPresentation("entry_triggered", 100, { stale: true }).label, "Blocked");
  assert.equal(isStalePrice("2026-07-23T00:00:00Z", Date.parse("2026-07-28T18:00:00Z")), true);
  assert.equal(isStalePrice("2026-07-28T12:00:00Z", Date.parse("2026-07-28T18:00:00Z")), false);
});

test("no-setup and unavailable states give a safe no-action explanation", () => {
  const source = readFileSync(new URL("../src/components/BeginnerSetup.tsx", import.meta.url), "utf8");
  assert.match(source, /No valid setup today/);
  assert.match(source, /The correct action is to wait/);
  assert.match(source, /Data unavailable/);
  assert.match(source, /Do not act until current prices/);
});

test("beginner glossary explains remaining trading jargon without probability claims", () => {
  const setupSource = readFileSync(new URL("../src/components/BeginnerSetup.tsx", import.meta.url), "utf8");
  const chartSource = readFileSync(new URL("../src/components/TradingChart.tsx", import.meta.url), "utf8");
  for (const term of ["EMA20", "EMA50", "Signal-time confidence", "Risk-on market", "Market regime", "Pullback"]) {
    assert.equal(setupSource.includes(term), true, `missing beginner definition for ${term}`);
  }
  assert.match(setupSource, /not the chance of making a profit/);
  assert.match(chartSource, /EMA20: "A recent average price/);
  assert.match(chartSource, /EMA50: "A longer average price/);
});
