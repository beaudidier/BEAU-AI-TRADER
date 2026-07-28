import { expect, test, type Page, type Route } from "@playwright/test";

type Scenario = "waiting" | "ready" | "blocked" | "expired" | "stale" | "portfolio";

const basePlan = {
  ticker: "TEST", signal_price: 101, current_price: 100, proposed_executable_entry: 100,
  entry: 100, stop_loss: 98, target_1: 104, target_2: 106, risk_per_share: 2,
  reward_to_target_1: 4, reward_to_target_2: 6, risk_reward_target_1: 2, risk_reward_target_2: 3,
  position_size: 10, total_position_value: 1000, maximum_risk: 20, account_risk_percent: 1,
  recommendation: "BUY", confidence_score: 80, reasons: [], warnings: [], trade_allowed: true,
  rejection_reasons: [],
  explanation: {
    verdict: "Review", summary: "Rules passed.", strengths: [], weaknesses: [],
    risks: ["The trend may reverse and reach the stop loss."], invalidation: "Below the stop.",
    next_trigger: "Entry", confidence_explanation: "Rule alignment only.",
  },
};

function signal(status: string, id = "best-setup") {
  const stale = status === "stale";
  const normalized = status === "ready" || stale || status === "portfolio" ? "entry_triggered"
    : status === "blocked" ? "invalidated" : status === "waiting" ? "waiting_for_entry" : "expired";
  return {
    id, ticker: id === "other-setup" ? "OTHER" : "TEST", company_name: id === "other-setup" ? "Other Corp" : "Test Company",
    sector: "Technology", signal_date: "2026-07-28", setup_status: normalized,
    current_price: 100, planned_entry: 100, distance_to_entry_percent: 0, expiry_date: "2026-07-31",
    invalidation: "Price broke the setup.", data_timestamp: stale ? "2026-07-20T00:00:00Z" : new Date().toISOString(),
    signal_timestamp: "2026-07-28T10:00:00Z", market_regime: "bullish", market_regime_score: 1,
    signal_price: 101, confidence: id === "other-setup" ? 70 : 80, risk_percent: 2,
    risk_reward_target_1: 2, risk_reward_target_2: 3,
    levels: { ema20: 100, ema50: 98, pullback_entry: 100, swing_low: 96, stop: 98, tp1: 104, tp2: 106 },
    qualification_reasons: ["Trend and pullback rules passed."], strategy_version: "frozen",
    chart: { public_url: "", window_start: "", window_end: "" }, checks: {},
    setup: {
      status: normalized, instruction: "", actionable_at_market: normalized === "entry_triggered",
      current_price: 100, current_price_timestamp: new Date().toISOString(), planned_entry: 100,
      distance_to_entry_percent: 0, distance_to_entry_label: "at entry", expiry_date: "2026-07-31",
      invalidation: "Price broke the setup.",
      beginner_explanation: {
        why_setup_exists: "The trend and pullback rules passed.",
        why_waiting_matters: "Wait for the planned price.",
        if_price_never_reaches_entry: "No trade opens.",
        why_buying_early_changes_risk_reward: "Buying early changes the risk.",
      },
    },
  };
}

function portfolio(blocked = false) {
  return {
    initial_balance: 10000, cash_balance: 10000, portfolio_balance: 10000,
    unrealized_pnl: 0, realized_pnl: 0, today_pnl: 0, win_rate: 0,
    open_positions: [], closed_positions: [], recent_trades: [], risk_rejections: [],
    portfolio_risk: {
      risk_status: blocked ? "BLOCKED" : "NORMAL",
      blocked_reasons: blocked ? ["Daily portfolio risk limit reached."] : [],
      open_positions: 0, open_risk_r: 0, open_risk_currency: 0, risk_unit_currency: 100,
      daily_new_risk_used_r: blocked ? 1 : 0, remaining_daily_risk_budget_r: blocked ? 0 : 1,
      current_equity: 10000, peak_equity: 10000, current_drawdown: 0, current_drawdown_r: 0,
      capacity_resets_at: "2026-07-29T00:00:00Z", limiting_positions: [], as_of: new Date().toISOString(),
      limits: { maximum_concurrent_positions: 10, maximum_total_open_risk_r: 10, maximum_daily_new_risk_r: 1, ranking: "confidence" },
    },
  };
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function installApi(page: Page, scenario: Scenario, initialMode: unknown = "beginner") {
  let preference = initialMode;
  let opened = false;
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === "/latest-signals/summary.json") {
      return json(route, {
        all_checks_passed: true,
        signals: scenario === "ready"
          ? [signal(scenario), signal("waiting", "other-setup")]
          : [signal(scenario)],
      });
    }
    if (url.pathname.endsWith("/me/settings")) {
      if (request.method() === "PATCH") {
        preference = (request.postDataJSON() as { experience_mode?: unknown }).experience_mode;
      }
      return json(route, {
        user_id: "beginner-e2e-user", default_account_size: 10000, default_risk_percent: 1,
        preferred_currency: "USD", theme: "dark",
        ...(preference === null ? {} : { experience_mode: preference }),
      });
    }
    if (url.pathname.endsWith("/me/paper-trading/portfolio")) return json(route, portfolio(scenario === "portfolio"));
    if (url.pathname.endsWith("/me/paper-trading/open")) {
      opened = true;
      return json(route, { id: "paper-trade-1" }, 201);
    }
    if (url.pathname.startsWith("/trade-plan/")) return json(route, basePlan);
    if (url.hostname === "127.0.0.1" && url.port === "8000") {
      return json(route, { detail: "Unused e2e endpoint" }, 404);
    }
    return route.continue();
  });
  return { getPreference: () => preference, wasOpened: () => opened };
}

test.describe("Beginner Mode end-to-end safety", () => {
  for (const [scenario, action] of [
    ["waiting", "Wait for entry"],
    ["blocked", "Setup blocked"],
    ["expired", "Setup expired"],
    ["stale", "Setup blocked"],
    ["portfolio", "Setup blocked"],
  ] as const) {
    test(`${scenario} is fail-closed with the correct primary action`, async ({ page }) => {
      const api = await installApi(page, scenario);
      await page.goto("/dashboard");
      const button = page.getByRole("button", { name: action, exact: true });
      await expect(button).toBeVisible();
      await expect(button).toBeDisabled();
      await expect(page.getByRole("button", { name: /buy now|real money/i })).toHaveCount(0);
      expect(api.wasOpened()).toBe(false);
    });
  }

  test("ready flow exposes every risk field and opens only a paper trade", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const api = await installApi(page, "ready");
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "TEST Test Company" })).toHaveCount(1);
    await expect(page.getByRole("heading", { name: /OTHER/ })).toHaveCount(0);
    const reviewButton = page.getByRole("button", { name: "Review paper trade" });
    const reviewBox = await reviewButton.boundingBox();
    expect(reviewBox && reviewBox.y + reviewBox.height).toBeLessThanOrEqual(900);
    await reviewButton.click();
    const dialog = page.getByRole("dialog", { name: /review test paper trade/i });
    await expect(dialog).toBeVisible();
    for (const field of ["Amount invested", "Quantity", "Planned entry", "Stop loss", "Maximum loss", "Risk percentage", "TP1", "TP2", "Risk / reward", "Why this trade may fail"]) {
      await expect(dialog.getByText(field, { exact: true })).toBeVisible();
    }
    await expect(dialog).toContainText("Paper trading only");
    const confirmButton = dialog.getByRole("button", { name: "Confirm paper trade" });
    const confirmBox = await confirmButton.boundingBox();
    expect(confirmBox && confirmBox.y + confirmBox.height).toBeLessThanOrEqual(900);
    await confirmButton.click();
    await expect(page.getByText("Paper trade opened. No real money was used.")).toBeVisible();
    expect(api.wasOpened()).toBe(true);
  });

  test("keyboard-only flow has named controls, ordered focus, and visible focus styling", async ({ page }) => {
    await installApi(page, "ready");
    await page.goto("/dashboard");
    const beginner = page.getByRole("button", { name: "beginner", exact: true });
    for (let index = 0; index < 20 && !await beginner.evaluate((element) => element === document.activeElement); index += 1) {
      await page.keyboard.press("Tab");
    }
    await expect(beginner).toBeFocused();
    expect(await beginner.evaluate((element) => getComputedStyle(element).boxShadow)).not.toBe("none");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "advanced", exact: true })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Confidence" })).toBeFocused();
  });

  test("390px mobile layout remains readable without horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installApi(page, "ready");
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "One setup. Clear risk. No real money." })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await expect(page.getByRole("button", { name: "Review paper trade" })).toBeVisible();
  });

  test("copy is paper-only and contains no certainty or live-ready claims", async ({ page }) => {
    await installApi(page, "ready");
    await page.goto("/dashboard");
    await expect(page.getByRole("button", { name: "Review paper trade" })).toBeVisible();
    const text = (await page.locator("body").innerText()).toLowerCase();
    expect(text).toContain("paper trading only");
    expect(text).toContain("not a probability");
    expect(text).not.toMatch(/\bguaranteed profit\b|\blive-ready\b/);
  });
});

test.describe("mode preference compatibility", () => {
  test("switch persists through refresh and a new authenticated session", async ({ browser, page }) => {
    const api = await installApi(page, "ready", "beginner");
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "advanced", exact: true }).click();
    await expect(page.getByRole("heading", { name: "What should I buy today?" })).toBeVisible();
    expect(api.getPreference()).toBe("advanced");
    await page.reload();
    await expect(page.getByRole("heading", { name: "What should I buy today?" })).toBeVisible();
    const nextContext = await browser.newContext();
    const nextPage = await nextContext.newPage();
    await installApi(nextPage, "ready", api.getPreference());
    await nextPage.goto("/dashboard");
    await expect(nextPage.getByRole("heading", { name: "What should I buy today?" })).toBeVisible();
    await nextContext.close();
  });

  for (const preference of [null, "unknown-mode"]) {
    test(`missing or invalid preference ${String(preference)} safely preserves Advanced Mode`, async ({ page }) => {
      await installApi(page, "ready", preference);
      await page.goto("/dashboard");
      await expect(page.getByRole("heading", { name: "What should I buy today?" })).toBeVisible();
      await expect(page.getByText("Advanced Mode", { exact: true })).toBeVisible();
    });
  }
});
