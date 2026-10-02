/** Record actual interactions against a running FinPulse preview.
 * NARRATION_PREFIX points to matching .json/.wav/.vtt files with measured chapter times.
 * Requires ffmpeg, Chromium, and Playwright's ffmpeg browser dependency.
 */
import { mkdir, readFile, copyFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { chromium, expect } from '@playwright/test';

const base = process.env.BASE_URL || 'http://127.0.0.1:5174/finpulse/';
const narration = process.env.NARRATION_PREFIX;
if (!narration) throw new Error('Set NARRATION_PREFIX to the generated narration files.');
const schedule = JSON.parse(await readFile(`${narration}.json`, 'utf8'));
const chapters = schedule.chapters;
const timing = (id, progress = 0) => {
  const chapter = chapters.find((item) => item.id === id);
  if (!chapter) throw new Error(`Missing chapter: ${id}`);
  return chapter.start + chapter.duration * progress;
};
await mkdir('output/recording', { recursive: true });
await mkdir('public/demo', { recursive: true });
const browser = await chromium.launch({
  headless: true,
  ...(process.env.BROWSER_PATH ? { executablePath: process.env.BROWSER_PATH } : {}),
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: 'reduce',
});
await context.addInitScript(() => {
  Element.prototype.requestPointerLock = () =>
    Promise.reject(new Error('Disabled during recording'));
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
});
const page = await context.newPage();
page.setDefaultTimeout(10000);
page.setDefaultNavigationTimeout(45000);
let started;
async function at(seconds, action) {
  const delay = started + seconds * 1000 - Date.now();
  if (delay > 0) await page.waitForTimeout(delay);
  else if (delay < -1800)
    throw new Error(`Recording fell behind at ${seconds}s. Retry without competing workloads.`);
  if (action) await action();
}
async function nav(name) {
  await page
    .getByRole('navigation', { name: 'Workspace navigation' })
    .getByRole('button', { name, exact: false })
    .click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
}
async function chapter(index, label) {
  await page.evaluate(
    ({ index, label }) => {
      document.getElementById('recording-chapter')?.remove();
      const badge = document.createElement('div');
      badge.id = 'recording-chapter';
      badge.textContent = `${String(index).padStart(2, '0')} / 10    ${label}`;
      badge.style.cssText =
        'position:fixed;right:22px;bottom:22px;padding:11px 16px;border:1px solid #d3def3;border-radius:7px;background:#fbfcfff7;color:#305599;font:500 13px "DM Sans",sans-serif;z-index:2147483647;pointer-events:none;box-shadow:0 3px 15px #14274412';
      (document.querySelector('dialog[open]') || document.body).appendChild(badge);
    },
    { index, label },
  );
  console.log(`${index}/10 ${label}`);
}
try {
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.stats-grid .stat')).toHaveCount(4, { timeout: 20000 });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: 'public/demo/workspace.jpg', type: 'jpeg', quality: 93 });
  await page.screencast.start({
    path: 'output/recording/finpulse-browser.webm',
    size: { width: 1440, height: 1000 },
  });
  started = Date.now();
  await chapter(1, 'FinPulse · Follow the signal');
  await at(timing('introduction', 0.45), async () => {
    await page
      .getByRole('group', { name: 'Trace stage' })
      .getByRole('button', { name: 'Quality', exact: true })
      .click();
  });
  await at(timing('introduction', 0.72), async () => {
    await page
      .getByRole('group', { name: 'Trace stage' })
      .getByRole('button', { name: 'Output', exact: true })
      .click();
  });
  await at(timing('overview'), async () => {
    await chapter(2, 'Five markets · One operating picture');
  });
  await at(timing('overview', 0.15), async () => {
    await page.getByLabel('Market filter').selectOption('KEN');
  });
  await at(timing('overview', 0.42), async () => {
    await page.getByLabel('Market filter').selectOption('all');
    await page.locator('.stats-grid').scrollIntoViewIfNeeded();
  });
  await at(timing('events'), async () => {
    await nav('Event explorer');
    await chapter(3, 'Every number has a source');
  });
  await at(timing('events', 0.2), async () => {
    await page.locator('.table-link').first().click();
    await page.getByRole('tab', { name: 'Original payload', exact: true }).click();
    await chapter(3, 'Inspect the original envelope');
  });
  await at(timing('events', 0.9), async () => {
    await page.keyboard.press('Escape');
  });
  await at(timing('simulate'), async () => {
    await page.getByRole('button', { name: 'Generate events', exact: true }).first().click();
    await page.getByRole('button', { name: /Quality incident/ }).click();
    await page.getByLabel('Batch size').fill('5');
    await chapter(4, 'Introduce a controlled quality incident');
  });
  await at(timing('simulate', 0.62), async () => {
    await page.getByRole('button', { name: 'Stage events', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await chapter(4, 'Raw events staged · Original input preserved');
  });
  await at(timing('pipeline'), async () => {
    await page.getByRole('button', { name: 'Run pipeline', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Run pipeline', exact: true })).toBeDisabled();
    await chapter(5, 'Real validation · Inspectable processing');
  });
  await at(timing('pipeline', 0.3), async () => {
    await page.locator('.flow-node').nth(2).click();
    await page.locator('.pipeline-canvas').scrollIntoViewIfNeeded();
  });
  await at(timing('pipeline', 0.65), async () => {
    await page.screenshot({
      path: 'public/demo/poster.jpg',
      type: 'jpeg',
      quality: 93,
      style: '#recording-chapter { visibility: hidden; }',
    });
  });
  await at(timing('quality'), async () => {
    await nav('Quality lab');
    await chapter(6, 'Exceptions with an explanation');
  });
  await at(timing('quality', 0.65), async () => {
    await page.getByRole('button', { name: 'Review correction', exact: true }).first().click();
    await chapter(6, 'Inspect the proposed correction');
  });
  await at(timing('replay'), async () => {
    await chapter(7, 'Human approval · Traceable replay');
  });
  await at(timing('replay', 0.5), async () => {
    await page.getByRole('button', { name: 'Approve replay', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await chapter(7, 'Correction validated · Audit trail preserved');
  });
  await at(timing('markets'), async () => {
    await nav('Market insights');
    await chapter(8, 'Compare the markets. Respect the currencies.');
  });
  await at(timing('markets', 0.25), async () => {
    await page.getByLabel('Comparison metric').selectOption('approvalRate');
  });
  await at(timing('markets', 0.52), async () => {
    await page.getByLabel('Market filter').selectOption('KEN');
  });
  await at(timing('markets', 0.8), async () => {
    await page.getByLabel('Market filter').selectOption('all');
  });
  await at(timing('lineage'), async () => {
    await nav('Data products');
    await page.getByRole('button', { name: /Customer features/ }).click();
    await chapter(9, 'Useful data, with its lineage');
  });
  await at(timing('lineage', 0.2), async () => {
    await page.getByRole('tab', { name: 'Lineage', exact: true }).click();
  });
  await at(timing('lineage', 0.5), async () => {
    await page.getByRole('tab', { name: 'Schema', exact: true }).click();
  });
  await at(timing('lineage', 0.78), async () => {
    await page.getByRole('link', { name: 'Download CSV', exact: true }).click();
  });
  await at(timing('closing'), async () => {
    await nav('Pulse overview');
    await chapter(10, 'Explore the workspace · Inspect the engineering');
  });
  await at(schedule.duration + 0.3);
  await page.screencast.stop();
} catch (error) {
  await page.screenshot({ path: 'output/recording/failure.png', fullPage: true }).catch(() => {});
  console.error(
    (
      await page
        .locator('body')
        .innerText()
        .catch(() => '')
    ).slice(0, 2400),
  );
  throw error;
} finally {
  await page.screencast.stop().catch(() => {});
  await context.close();
  await browser.close();
}
await new Promise((resolve, reject) => {
  const proc = spawn(
    'ffmpeg',
    [
      '-hide_banner',
      '-loglevel',
      'warning',
      '-y',
      '-i',
      'output/recording/finpulse-browser.webm',
      '-i',
      `${narration}.wav`,
      '-i',
      `${narration}.vtt`,
      '-map',
      '0:v:0',
      '-map',
      '1:a:0',
      '-map',
      '2:s:0',
      '-vf',
      'fps=25,format=yuv420p',
      '-c:v',
      'libx264',
      '-preset',
      'medium',
      '-crf',
      '18',
      '-threads',
      '2',
      '-c:a',
      'aac',
      '-b:a',
      '128k',
      '-c:s',
      'mov_text',
      '-metadata:s:s:0',
      'language=eng',
      '-metadata',
      'title=FinPulse — Follow the signal',
      '-t',
      String(schedule.duration),
      '-movflags',
      '+faststart',
      'public/demo/finpulse-demo.mp4',
    ],
    { stdio: 'inherit' },
  );
  proc.on('error', reject);
  proc.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}`))));
});
await copyFile(`${narration}.vtt`, 'public/demo/finpulse-demo.vtt');
console.log(
  `Recorded public/demo/finpulse-demo.mp4 (${schedule.duration}s), with narration and captions.`,
);
