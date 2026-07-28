import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../src/pages/PaperTradingPage.tsx", import.meta.url), "utf8");
const review = readFileSync(new URL("../src/pages/TradeReviewPage.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/services/userApi.ts", import.meta.url), "utf8");
const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");

test("position, Coach and chart navigation are wired", () => {
  assert.match(page, /navigate\(`\/journal\/\$\{t\.id\}`\)/);
  assert.match(page, /#coach/);
  assert.match(page, /navigate\(`\/workspace\/\$\{t\.ticker\}`\)/);
  assert.match(app, /journal\/:tradeId/);
});

test("journal persistence and user-safe API payload are wired", () => {
  assert.match(review, /updatePaperTradeJournal/);
  assert.match(review, /setup_tags/);
  assert.match(review, /mistake_tags/);
  assert.match(review, /emotion_tags/);
  assert.doesNotMatch(review, /user_id/);
  assert.match(api, /method: "PATCH"/);
});

test("filters, three exports and responsive layouts are present", () => {
  for (const term of ["search", "strategy", "result", "status", "tag", "grade", "setup", "from", "to"]) assert.match(page, new RegExp(term));
  for (const file of ["full-journal.csv", "open-positions.csv", "closed-positions.csv"]) assert.match(page, new RegExp(file.replace(".", "\\.")));
  assert.match(page, /sm:grid-cols-2/);
  assert.match(page, /overflow-x-auto/);
});

test("CSV values are escaped and spreadsheet formulas are neutralized", () => {
  assert.match(page, /\^\[\\t\\r \]\*\[=\+\\-@\]/);
  assert.match(page, /replaceAll\('"', '""'\)/);
  assert.match(page, /map\(safeCsvValue\)/);
  assert.match(page, /const rows = useMemo\(\(\) => filterJournalTrades/);
  assert.match(page, /exportTradesCsv\("full-journal\.csv", rows\)/);
});
