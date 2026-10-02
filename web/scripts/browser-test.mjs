import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium, expect as playwrightExpect } from '@playwright/test';

const base = (process.env.BASE_URL || 'http://127.0.0.1:5174/finpulse/').replace(/\/?$/, '/');
const browser = await chromium.launch({
  headless: true,
  ...(process.env.BROWSER_PATH ? { executablePath: process.env.BROWSER_PATH } : {}),
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: 'reduce',
});
const page = await context.newPage();
page.setDefaultTimeout(15000);
const expect = playwrightExpect.configure({ timeout: 15000 });
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
await mkdir('output/review', { recursive: true });
const routes = [
  ['overview', 'Pulse overview'],
  ['events', 'Event explorer'],
  ['quality', 'Quality lab'],
  ['pipeline', 'Pipeline studio'],
  ['markets', 'Market insights'],
  ['products', 'Data products'],
];
const workspace = () =>
  page.evaluate(
    async (prefix) => (await fetch(`${prefix}api/workspace`)).json(),
    new URL(base).pathname,
  );
async function nav(label) {
  if ((await page.viewportSize()).width <= 800)
    await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  await page
    .getByRole('navigation', { name: 'Workspace navigation' })
    .getByRole('button', { name: label, exact: false })
    .click();
  await expect(page.getByRole('heading', { name: label, exact: true })).toBeVisible();
}
async function scenario(name) {
  await nav('Pipeline studio');
  await page.getByRole('button', { name: 'Generate events', exact: true }).click();
  await page.getByRole('button', { name, exact: false }).click();
  await page.getByLabel('Batch size').fill('5');
  await page.getByRole('button', { name: 'Stage events', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Run pipeline', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Run pipeline', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Run pipeline', exact: true })).toBeDisabled();
}
try {
  await page.goto(base, { waitUntil: 'networkidle' });
  await expect(page.locator('.stats-grid .stat')).toHaveCount(4);
  await page.evaluate(() => document.fonts.ready);
  const first = await workspace();
  assert.ok(first.stats.accepted > 500);
  const initialId = await page.locator('.lens-document-head > span').first().innerText();
  await page
    .getByRole('group', { name: 'Trace stage' })
    .getByRole('button', { name: 'Quality', exact: true })
    .click();
  await expect(page.locator('.lens-detail')).toContainText('Disposition');
  await page
    .getByRole('group', { name: 'Trace stage' })
    .getByRole('button', { name: 'Output', exact: true })
    .click();
  await expect(page.locator('.lens-document-head > span').first()).toHaveText(initialId);
  await page.getByRole('button', { name: 'Open original event', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await page
    .getByRole('group', { name: 'Trace stage' })
    .getByRole('button', { name: 'Source', exact: true })
    .click();
  await page.screenshot({ path: 'output/review/overview-desktop.png', fullPage: true });
  if (!process.env.SKIP_ASSET_CAPTURE)
    await page.screenshot({ path: 'public/demo/workspace.jpg', type: 'jpeg', quality: 93 });
  await nav('Event explorer');
  await page.getByLabel('Delivery status').selectOption('accepted');
  await expect(page.locator('tbody tr')).toHaveCount(25);
  await page.locator('.table-link').first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('tab', { name: 'Original payload', exact: true }).click();
  await expect(page.locator('.code-panel')).toContainText('event_id');
  await page.keyboard.press('Escape');
  await scenario('Quality incident');
  let result = await workspace();
  assert.equal(result.stats.openQuarantine, first.stats.openQuarantine + 5);
  assert.equal(result.stats.accepted, first.stats.accepted);
  await page.locator('.flow-node').nth(2).click();
  await expect(page.locator('.step-inspector')).toBeVisible();
  await page.screenshot({ path: 'output/review/pipeline-desktop.png', fullPage: true });
  if (!process.env.SKIP_ASSET_CAPTURE)
    await page.screenshot({ path: 'public/demo/poster.jpg', type: 'jpeg', quality: 93 });
  await nav('Quality lab');
  await page.getByRole('button', { name: 'Review correction', exact: true }).first().click();
  await expect(page.locator('.correction')).toContainText('ingested_at');
  await page.getByRole('button', { name: 'Approve replay', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  result = await workspace();
  assert.equal(result.stats.openQuarantine, first.stats.openQuarantine + 4);
  assert.equal(result.stats.accepted, first.stats.accepted + 1);
  assert.ok(result.audit.some((row) => /replay|correct/i.test(row.action)));
  const beforeDuplicate = result.stats;
  await scenario('Duplicate delivery');
  result = await workspace();
  assert.equal(result.stats.accepted, beforeDuplicate.accepted);
  assert.equal(result.stats.duplicates, beforeDuplicate.duplicates + 5);
  const beforeLate = result.stats;
  await scenario('Late arrival');
  result = await workspace();
  assert.equal(result.stats.accepted, beforeLate.accepted + 5);
  assert.equal(result.stats.late, beforeLate.late + 5);
  await scenario('Everyday activity');
  assert.equal((await workspace()).stats.accepted, result.stats.accepted + 5);
  await nav('Market insights');
  await page.getByLabel('Market filter').selectOption('KEN');
  await expect(page.locator('.market-table tbody tr')).toHaveCount(1);
  await expect(page.locator('.market-table')).toContainText('KES');
  await page.getByLabel('Market filter').selectOption('all');
  await nav('Data products');
  await page.getByRole('button', { name: /Customer features/ }).click();
  await expect(page.locator('.product-detail')).toContainText('Gsm Observations');
  await page.getByRole('tab', { name: 'Schema', exact: true }).click();
  await expect(page.locator('.schema-list')).toContainText('customer_id');
  await page.getByRole('tab', { name: 'Lineage', exact: true }).click();
  await expect(page.locator('.product-lineage')).toContainText('Immutable deliveries');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download CSV', exact: true }).click();
  const download = await downloadPromise;
  await download.saveAs('output/review/features.csv');
  assert.match(download.suggestedFilename(), /features/);
  const other = await browser.newContext();
  const otherPage = await other.newPage();
  await otherPage.goto(base, { waitUntil: 'networkidle' });
  await otherPage.screenshot({ path: 'output/review/isolated-visitor.png' });
  assert.ok(
    !(await otherPage.locator('.error-panel').count()),
    await otherPage.locator('body').innerText(),
  );
  await expect(otherPage.locator('.stats-grid .stat')).toHaveCount(4, { timeout: 15000 });
  const untouched = await otherPage.evaluate(
    async (prefix) => (await fetch(`${prefix}api/workspace`)).json(),
    new URL(base).pathname,
  );
  assert.equal(
    untouched.stats.received,
    first.stats.received,
    'Second visitor has a fresh dataset',
  );
  await other.close();
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const [route, label] of routes) {
      await nav(label);
      await page.evaluate(() => document.fonts.ready);
      const size = await page.evaluate(() => ({
        width: innerWidth,
        scroll: document.documentElement.scrollWidth,
      }));
      assert.ok(
        size.scroll <= size.width + 1,
        `${route} overflow at${width}px: ${JSON.stringify(size)}`,
      );
      if (width === 390 || width === 1440)
        await page.screenshot({ path: `output/review/${route}-${width}.png`, fullPage: true });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.keyboard.press('Control+k');
  await page.getByLabel('Search sections').fill('quality');
  await page.locator('.command-results button').click();
  await expect(page.getByRole('heading', { name: 'Quality lab', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reset demo', exact: true }).click();
  await page.getByRole('button', { name: 'Reset my workspace', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  assert.equal((await workspace()).stats.received, first.stats.received);
  assert.deepEqual(errors, []);
  console.log(
    'Passed:6sections,4scenarios, staged validation, approved correction, deduplication, late-warning behavior, market filter, real product previews/export, isolated visitors,5viewport widths, quick navigation and reset.',
  );
} catch (error) {
  await page.screenshot({ path: 'output/review/failure.png', fullPage: true }).catch(() => {});
  console.error('Browser errors:', errors);
  throw error;
} finally {
  await browser.close();
}
