#!/usr/bin/env node
/**
 * render_pin.js — Renders HTML content to PNG using Puppeteer (headless Chromium).
 *
 * Called by pin_assembler.py via subprocess. Two modes:
 *
 *   Single:  node render_pin.js --html-file <path> --output <path> [--width 1000] [--height 1500] [--wait 500]
 *   Batch:   node render_pin.js --manifest <path>
 *
 * Manifest JSON format:
 *   [{"html_file": "...", "output_file": "...", "width": 1000, "height": 1500, "wait_ms": 500}, ...]
 *
 * Outputs JSON to stdout on success: {"ok": true, "rendered": ["path1.png", ...]}
 * Outputs JSON to stdout on failure: {"ok": false, "error": "message"}
 */

const puppeteer = require("puppeteer");
const fs = require("fs");
const path = require("path");

const DEFAULT_WIDTH = 1000;
const DEFAULT_HEIGHT = 1500;
const DEFAULT_WAIT_MS = 500;

async function renderOne(browser, { html_file, output_file, width, height, wait_ms }) {
  const w = width || DEFAULT_WIDTH;
  const h = height || DEFAULT_HEIGHT;
  const waitMs = wait_ms || DEFAULT_WAIT_MS;

  const html = fs.readFileSync(html_file, "utf-8");

  // Ensure output directory exists
  const outDir = path.dirname(output_file);
  fs.mkdirSync(outDir, { recursive: true });

  const page = await browser.newPage();
  await page.setViewport({ width: w, height: h });
  await page.setContent(html, { waitUntil: "domcontentloaded" });

  // Brief wait for web fonts to load
  if (waitMs > 0) {
    await new Promise((r) => setTimeout(r, waitMs));
  }

  await page.screenshot({
    path: output_file,
    clip: { x: 0, y: 0, width: w, height: h },
    type: "png",
  });

  await page.close();
  return output_file;
}

async function main() {
  const args = process.argv.slice(2);

  let jobs = [];

  // Parse arguments
  const idx = (flag) => args.indexOf(flag);

  if (idx("--manifest") !== -1) {
    const manifestPath = args[idx("--manifest") + 1];
    jobs = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  } else if (idx("--html-file") !== -1) {
    jobs = [
      {
        html_file: args[idx("--html-file") + 1],
        output_file: args[idx("--output") + 1],
        width: idx("--width") !== -1 ? parseInt(args[idx("--width") + 1]) : DEFAULT_WIDTH,
        height: idx("--height") !== -1 ? parseInt(args[idx("--height") + 1]) : DEFAULT_HEIGHT,
        wait_ms: idx("--wait") !== -1 ? parseInt(args[idx("--wait") + 1]) : DEFAULT_WAIT_MS,
      },
    ];
  } else {
    console.log(JSON.stringify({ ok: false, error: "Usage: --html-file <path> --output <path> | --manifest <path>" }));
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--font-render-hinting=none",
    ],
  });

  const rendered = [];
  const errors = [];

  for (const job of jobs) {
    try {
      const out = await renderOne(browser, job);
      rendered.push(out);
    } catch (e) {
      errors.push({ file: job.output_file, error: e.message });
    }
  }

  await browser.close();

  if (errors.length > 0) {
    console.log(JSON.stringify({ ok: false, rendered, errors }));
    process.exit(errors.length === jobs.length ? 1 : 0);
  } else {
    console.log(JSON.stringify({ ok: true, rendered }));
  }
}

main().catch((e) => {
  console.log(JSON.stringify({ ok: false, error: e.message }));
  process.exit(1);
});
