#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const VIEWPORT = { width: 2000, height: 900 };
const FRAME = 56;
const FIXED_NOW = "2026-07-10T17:00:00Z";
const STYLES = ["editorial", "gold", "ink"];

function argument(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const outputDir = path.resolve(argument("--out-dir", path.join(ROOT, "docs/screenshots")));
const requestedStyle = argument("--style", "ink");
const releaseNames = process.argv.includes("--release");
const styles = requestedStyle === "all" ? STYLES : [requestedStyle];
if (!styles.every((style) => STYLES.includes(style))) {
  throw new Error(`Unknown style: ${requestedStyle}. Choose ${STYLES.join(", ")}, or all.`);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: ROOT, encoding: "utf8", ...options });
  if (result.status !== 0) {
    throw new Error(`${command} failed:\n${result.stderr || result.stdout}`);
  }
  return result.stdout.trim();
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class CdpClient {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async open() {
    await new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(message.error.message));
        else pending.resolve(message.result);
        return;
      }
      const waiters = this.listeners.get(message.method) || [];
      this.listeners.delete(message.method);
      waiters.forEach((resolve) => resolve(message.params));
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  once(method) {
    return new Promise((resolve) => {
      const waiters = this.listeners.get(method) || [];
      waiters.push(resolve);
      this.listeners.set(method, waiters);
    });
  }
}

async function waitForPort(profileDir) {
  const portFile = path.join(profileDir, "DevToolsActivePort");
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const [port] = (await readFile(portFile, "utf8")).trim().split("\n");
      if (port) return port;
    } catch {}
    await delay(50);
  }
  throw new Error("Chrome did not publish its debugging port.");
}

async function navigate(client, url) {
  const loaded = client.once("Page.loadEventFired");
  await client.send("Page.navigate", { url });
  await loaded;
  await evaluate(client, "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))", {
    awaitPromise: true,
  });
}

async function evaluate(client, expression, options = {}) {
  const response = await client.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    ...options,
  });
  if (response.exceptionDetails) {
    const detail = response.exceptionDetails.exception?.description || response.exceptionDetails.text;
    throw new Error(`Chrome page evaluation failed: ${detail}`);
  }
  return response.result.value;
}

async function settle(client) {
  await evaluate(client, "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))", {
    awaitPromise: true,
  });
}

async function closeChrome(client, chrome) {
  if (client) await client.send("Browser.close").catch(() => {});
  if (chrome.exitCode === null) {
    await Promise.race([
      new Promise((resolve) => chrome.once("exit", resolve)),
      delay(2000),
    ]);
  }
  if (chrome.exitCode === null) chrome.kill("SIGTERM");
}

function fileName(theme, part, style = "") {
  if (releaseNames) {
    if (part === "annotated") return `release-demo-${theme}-annotated.png`;
    if (part === "thread") return `release-demo-thread-${theme}.png`;
  }
  return [theme, style, part].filter(Boolean).join("-") + ".png";
}

async function captureTheme(theme, viewPath, tempDir) {
  const profileDir = path.join(tempDir, `chrome-${theme}`);
  await mkdir(profileDir, { recursive: true });
  const chrome = spawn(CHROME, [
    "--headless=new",
    "--remote-debugging-port=0",
    `--user-data-dir=${profileDir}`,
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-extensions",
    "--hide-scrollbars",
    "--force-device-scale-factor=1",
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank",
  ], { stdio: "ignore" });

  let client;
  try {
    const port = await waitForPort(profileDir);
    const targets = await fetch(`http://127.0.0.1:${port}/json`).then((response) => response.json());
    const page = targets.find((target) => target.type === "page");
    if (!page) throw new Error("Chrome exposed no page target.");
    client = new CdpClient(page.webSocketDebuggerUrl);
    await client.open();
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: VIEWPORT.width,
      height: VIEWPORT.height,
      deviceScaleFactor: 1,
      mobile: false,
      screenWidth: VIEWPORT.width,
      screenHeight: VIEWPORT.height,
    });
    await client.send("Page.addScriptToEvaluateOnNewDocument", {
      source: `
        (() => {
          const NativeDate = Date;
          const fixedNow = ${JSON.stringify(FIXED_NOW)};
          class CaptureDate extends NativeDate {
            constructor(...args) { super(...(args.length ? args : [fixedNow])); }
            static now() { return new NativeDate(fixedNow).getTime(); }
          }
          globalThis.Date = CaptureDate;
          try {
            localStorage.setItem('mn-theme', ${JSON.stringify(theme)});
            localStorage.setItem('mn-reviewer', 'Aeva');
            localStorage.setItem('mn-text-scale', '1');
          } catch {}
        })();
      `,
    });

    await navigate(client, pathToFileURL(viewPath).href);
    await evaluate(client, `
        (() => {
          const open = document.querySelector('.mn-card[data-note="release-critical"] .mn-open-note');
          if (!open) throw new Error('Critical release note did not render.');
          open.click();
          const style = document.createElement('style');
          style.textContent = '*, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }';
          document.head.appendChild(style);
        })();
      `);
    await settle(client);

    const geometry = await evaluate(client, `
        (() => {
          const specs = ${JSON.stringify([
            [1, ".mn-armbar", 0, 0.02, 0.5],
            [2, "#margin-header", 0, 0.01, 0.5],
            [3, "#margin-doc h1", 0, 0, 0.5],
            [4, ".mn-toolbar-field", 2, 1, 0.5],
            [5, ".mn-rail-controls", 0, 1, 0.18],
            [6, ".mn-tabs", 0, 1, 0.5],
            [7, ".mn-card.active .mn-quote", 0, 1, 0.5],
            [8, ".mn-reader-tools", 0, 0, 0.5],
            [9, ".mn-card.active .mn-receipt", 0, 1, 0.5],
            [10, ".mn-card.active .mn-conv", 0, 1, 0.5],
            [11, ".mn-card.active .mn-composer", 0, 1, 0.5],
            [12, ".mn-map-list", 0, 0, 0.08],
          ])};
          const points = {};
          for (const [id, selector, index, fx, fy] of specs) {
            const node = document.querySelectorAll(selector)[index];
            if (!node) throw new Error('Missing callout target ' + id + ': ' + selector);
            const rect = node.getBoundingClientRect();
            points[id] = { x: rect.left + rect.width * fx, y: rect.top + rect.height * fy };
          }
          const card = document.querySelector('.mn-card.active').getBoundingClientRect();
          return { points, card: { x: card.left, y: card.top, width: card.width, height: card.height } };
        })()
      `);

    const basePath = path.join(tempDir, `${theme}-base.png`);
    const screenshot = await client.send("Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      captureBeyondViewport: false,
    });
    await writeFile(basePath, Buffer.from(screenshot.data, "base64"));

    const card = geometry.card;
    const inset = 12;
    const clip = {
      x: Math.max(0, card.x - inset),
      y: Math.max(0, card.y - inset),
      width: Math.min(VIEWPORT.width - Math.max(0, card.x - inset), card.width + inset * 2),
      height: card.height + inset * 2,
      scale: 1,
    };
    const thread = await client.send("Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      captureBeyondViewport: true,
      clip,
    });
    const threadPath = path.join(outputDir, fileName(theme, "thread"));
    await writeFile(threadPath, Buffer.from(thread.data, "base64"));

    return { basePath, points: geometry.points };
  } finally {
    await closeChrome(client, chrome);
  }
}

function markerPositions() {
  return {
    1: { x: 275, y: -28 },
    2: { x: -28, y: 118 },
    3: { x: 760, y: -28 },
    4: { x: 1190, y: -28 },
    5: { x: VIEWPORT.width + 28, y: 174 },
    6: { x: VIEWPORT.width + 28, y: 278 },
    7: { x: VIEWPORT.width + 28, y: 390 },
    8: { x: -28, y: 230 },
    9: { x: VIEWPORT.width + 28, y: 500 },
    10: { x: VIEWPORT.width + 28, y: 620 },
    11: { x: VIEWPORT.width + 28, y: 790 },
    12: { x: -28, y: 360 },
  };
}

function palette(style, theme) {
  const dark = theme === "dark";
  if (style === "gold") {
    return { line: "#ffd447", fill: "#ffd447", text: "#17130a", halo: dark ? "#111827" : "#ffffff" };
  }
  if (style === "ink") {
    return { line: dark ? "#f4ead5" : "#243149", fill: dark ? "#243149" : "#f8f2e6", text: dark ? "#ffffff" : "#182235", halo: dark ? "#111827" : "#ffffff" };
  }
  return { line: dark ? "#91adff" : "#3158c7", fill: dark ? "#24376b" : "#ffffff", text: dark ? "#ffffff" : "#173487", halo: dark ? "#101521" : "#ffffff" };
}

function annotationHtml(theme, style, basePath, points) {
  const colors = palette(style, theme);
  const markers = markerPositions();
  const width = VIEWPORT.width + FRAME * 2;
  const height = VIEWPORT.height + FRAME * 2;
  const arrows = Object.keys(markers).map((id) => {
    const marker = markers[id];
    const target = points[id];
    return `
      <line x1="${marker.x + FRAME}" y1="${marker.y + FRAME}" x2="${target.x + FRAME}" y2="${target.y + FRAME}" />
      <circle class="target" cx="${target.x + FRAME}" cy="${target.y + FRAME}" r="5" />
      <circle class="number" cx="${marker.x + FRAME}" cy="${marker.y + FRAME}" r="20" />
      <text x="${marker.x + FRAME}" y="${marker.y + FRAME + 1}">${id}</text>
    `;
  }).join("");
  const frameBackground = theme === "dark" ? "#101722" : "#e9eef5";
  return `<!doctype html>
    <html><head><meta charset="utf-8"><style>
      * { box-sizing: border-box; }
      html, body { width: ${width}px; height: ${height}px; margin: 0; overflow: hidden; }
      body { position: relative; background: ${frameBackground}; }
      img { position: absolute; left: ${FRAME}px; top: ${FRAME}px; width: ${VIEWPORT.width}px; height: ${VIEWPORT.height}px;
        border-radius: 14px; box-shadow: 0 18px 48px rgba(8, 12, 22, .28); }
      svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
      line { stroke: ${colors.line}; stroke-width: 3; marker-end: url(#arrow);
        filter: drop-shadow(0 1px 2px ${colors.halo}); }
      line + .target { fill: ${colors.line}; stroke: ${colors.halo}; stroke-width: 4; }
      .number { fill: ${colors.fill}; stroke: ${colors.line}; stroke-width: 3; filter: drop-shadow(0 2px 3px rgba(0,0,0,.28)); }
      text { fill: ${colors.text}; font: 800 20px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        text-anchor: middle; dominant-baseline: middle; }
    </style></head><body>
      <img src="${pathToFileURL(basePath).href}" alt="">
      <svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
        <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L8,4 L0,8 z" fill="${colors.line}" stroke="${colors.halo}" stroke-width="1" />
        </marker></defs>
        ${arrows}
      </svg>
    </body></html>`;
}

async function captureStaticHtml(htmlPath, outputPath) {
  const profileDir = path.join(path.dirname(htmlPath), `compose-${path.basename(htmlPath, ".html")}`);
  await mkdir(profileDir, { recursive: true });
  const chrome = spawn(CHROME, [
    "--headless=new",
    `--user-data-dir=${profileDir}`,
    "--allow-file-access-from-files",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-extensions",
    "--hide-scrollbars",
    "--force-device-scale-factor=1",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=0",
    "about:blank",
  ], { stdio: "ignore" });

  let client;
  try {
    const port = await waitForPort(profileDir);
    const targets = await fetch(`http://127.0.0.1:${port}/json`).then((response) => response.json());
    const page = targets.find((target) => target.type === "page");
    if (!page) throw new Error("Chrome exposed no composition target.");
    client = new CdpClient(page.webSocketDebuggerUrl);
    await client.open();
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: VIEWPORT.width + FRAME * 2,
      height: VIEWPORT.height + FRAME * 2,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await navigate(client, pathToFileURL(htmlPath).href);
    await evaluate(client, "Promise.all(Array.from(document.images, (image) => image.decode()))", {
      awaitPromise: true,
    });
    await settle(client);
    const screenshot = await client.send("Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      captureBeyondViewport: false,
    });
    await writeFile(outputPath, Buffer.from(screenshot.data, "base64"));
  } finally {
    await closeChrome(client, chrome);
  }
}

async function main() {
  await mkdir(outputDir, { recursive: true });
  const viewPath = run("bash", [path.join(ROOT, "scripts/build-release-demo.sh")]);
  const tempDir = await mkdtemp(path.join(os.tmpdir(), "marginalia-readme-"));
  try {
    for (const theme of ["dark", "light"]) {
      const capture = await captureTheme(theme, viewPath, tempDir);
      for (const style of styles) {
        const htmlPath = path.join(tempDir, `${theme}-${style}.html`);
        await writeFile(htmlPath, annotationHtml(theme, style, capture.basePath, capture.points));
        const outputPath = path.join(outputDir, fileName(theme, "annotated", style));
        await captureStaticHtml(htmlPath, outputPath);
        process.stdout.write(`${outputPath}\n`);
      }
    }
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}

await main();
