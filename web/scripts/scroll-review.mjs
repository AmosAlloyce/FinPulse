import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { chromium, expect } from '@playwright/test';

const base = process.env.BASE_URL || 'http://127.0.0.1:5174/finpulse/';
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.BROWSER_PATH || '/opt/brave.com/brave/brave',
});
const report = [];
try {
  for (const [name, width, height, reducedMotion] of [
    ['desktop', 1440, 1000, 'no-preference'],
    ['phone', 390, 844, 'no-preference'],
    ['compact', 360, 640, 'no-preference'],
    ['reduced', 1440, 1000, 'reduce'],
  ]) {
    const out = `output/scroll-review/${name}`;
    await mkdir(out, { recursive: true });
    const context = await browser.newContext({ viewport: { width, height }, reducedMotion });
    await context.addInitScript(() => {
      Element.prototype.requestPointerLock = () => Promise.reject(new Error('Disabled in review'));
      Element.prototype.setPointerCapture = () => {};
      Element.prototype.releasePointerCapture = () => {};
      Document.prototype.exitPointerLock = () => {};
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(base, { waitUntil: 'networkidle' });
    await expect(page.locator('.signal-lens')).toBeVisible({ timeout: 20000 });
    await page.evaluate(() => document.fonts.ready);
    const initial = await page.locator('.lens-document-head > span').first().innerText();
    for (const stage of ['Quality', 'Output', 'Source']) {
      await page
        .getByRole('group', { name: 'Trace stage' })
        .getByRole('button', { name: stage, exact: true })
        .focus();
      await page.keyboard.press('Enter');
      await expect(
        page
          .getByRole('group', { name: 'Trace stage' })
          .getByRole('button', { name: stage, exact: true }),
      ).toHaveAttribute('aria-pressed', 'true');
      assert.equal(await page.locator('.lens-document-head > span').first().innerText(), initial);
    }
    const total = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
    const positions = [0, 140, 320, Math.min(total, 620), Math.round(total * 0.72), total];
    const samples = [];
    for (let index = 0; index < positions.length; index++) {
      await page.evaluate((y) => scrollTo({ top: y, behavior: 'instant' }), positions[index]);
      await page.waitForTimeout(180);
      const dimensions = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth,
        width: innerWidth,
        transform: getComputedStyle(document.querySelector('.lens-backplane')).transform,
        progress: document.querySelector('.signal-lens').style.getPropertyValue('--lens-scroll'),
      }));
      assert.ok(dimensions.scroll <= dimensions.width + 1, `${name}: horizontal overflow`);
      if (reducedMotion === 'reduce') assert.equal(dimensions.transform, 'none');
      samples.push(dimensions);
      await page.screenshot({ path: `${out}/${String(index).padStart(2, '0')}.png` });
    }
    if (reducedMotion !== 'reduce')
      assert.notEqual(
        samples[0].transform,
        samples[3].transform,
        'Back plane changes at intermediate scroll',
      );
    assert.deepEqual(errors, []);
    await new Promise((resolve, reject) => {
      const proc = spawn('ffmpeg', [
        '-hide_banner',
        '-loglevel',
        'error',
        '-y',
        '-i',
        `${out}/%02d.png`,
        '-vf',
        `scale=${width < 600 ? 195 : 360}:-1,tile=3x2`,
        '-frames:v',
        '1',
        `${out}/sheet.png`,
      ]);
      proc.on('exit', (code) =>
        code === 0 ? resolve() : reject(new Error(`Contact sheet failed: ${code}`)),
      );
      proc.on('error', reject);
    });
    report.push({ name, width, height, reducedMotion, samples, errors });
    await context.close();
  }
  await writeFile('output/scroll-review/report.json', JSON.stringify(report, null, 2));
  console.log(
    'Passed 24 rendered scroll states, keyboard event trace, compact/mobile widths and reduced-motion fallback. Contact sheets in output/scroll-review.',
  );
} finally {
  await browser.close();
}
