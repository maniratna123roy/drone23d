/** Optional native Chrome/CDP smoke test. Uses a fixture backend, NOT a real video reconstruction.
 * Windows: node tests/browser-smoke.mjs
 * Other systems: CHROME_BIN=/path/to/chrome node tests/browser-smoke.mjs
 * No Playwright/Puppeteer, browser downloads, package installation, or backend changes.
 */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { manifest, status, binary, classes } from "./verified-fixtures.mjs";

const cwd = dirname(dirname(fileURLToPath(import.meta.url)));
const chrome =
  process.env.CHROME_BIN || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
if (!existsSync(chrome))
  throw new Error("Set CHROME_BIN to an already-installed Chrome/Chromium executable.");
const temp = mkdtempSync(join(tmpdir(), "spatial-verified-smoke-"));
const apiPort = 18765,
  vitePort = 18766,
  debugPort = 18767;
const children = [];
const requests = [];
let currentStatus = status();
let currentScene = { status: "empty", manifest: null };
const quads = binary([
  { position: [-2, 0, -10], scale: [1, 0.2, 0.1], color: [255, 35, 15, 180] },
  {
    position: [0, 0, -10],
    scale: [1, 0.2, 0.1],
    color: [25, 255, 35, 180],
    quaternion: [Math.SQRT1_2, 0, 0, Math.SQRT1_2],
  },
  { position: [2, 0, -10], scale: [1, 0.2, 0.1], color: [30, 65, 255, 180] },
]);
const server = createServer(async (request, response) => {
  requests.push(request.url);
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (request.method === "OPTIONS") {
    response.end();
    return;
  }
  if (request.url === "/api/pipeline/upload") {
    for await (const _chunk of request) {
      /* consume the local fixture upload */
    }
    currentStatus = status("processing", "browser-job");
    response.setHeader("Content-Type", "application/json");
    response.end(
      JSON.stringify({
        job_id: "browser-job",
        status: "processing",
        message: "Checking local camera geometry",
      }),
    );
  } else if (request.url === "/api/pipeline/status" || request.url === "/api/pipeline/scene") {
    response.setHeader("Content-Type", "application/json");
    response.end(JSON.stringify(request.url.endsWith("status") ? currentStatus : currentScene));
  } else if (request.url === "/static/scenes/browser-job/scene.splat")
    response.end(Buffer.from(quads));
  else if (request.url === "/static/scenes/browser-job/scene.classes.u8")
    response.end(Buffer.from(classes(3)));
  else {
    response.statusCode = 404;
    response.end();
  }
});
server.on("upgrade", (_request, socket) => socket.destroy()); // prove polling fallback without WebSocket
await new Promise((resolve) => server.listen(apiPort, "127.0.0.1", resolve));
let socket;
let viteLog = "";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function eventually(check, label, timeout = 60000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    try {
      const result = await check();
      if (result) return result;
    } catch {
      /* startup/navigation may race */
    }
    await sleep(150);
  }
  throw new Error(`Timed out: ${label}\n${viteLog.slice(-2500)}`);
}

try {
  const vite = spawn(
    process.execPath,
    [
      "node_modules/vite/bin/vite.js",
      "--host",
      "127.0.0.1",
      "--port",
      String(vitePort),
      "--strictPort",
    ],
    {
      cwd,
      env: {
        ...process.env,
        VITE_API_BASE_URL: `http://127.0.0.1:${apiPort}`,
        VITE_WS_URL: `ws://127.0.0.1:${apiPort}/ws/scene`,
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  children.push(vite);
  vite.stdout.on("data", (chunk) => {
    viteLog += chunk;
  });
  vite.stderr.on("data", (chunk) => {
    viteLog += chunk;
  });
  await eventually(
    async () => (await fetch(`http://127.0.0.1:${vitePort}/demo`)).ok,
    "Vite /demo startup",
  );
  children.push(
    spawn(
      chrome,
      [
        "--headless=new",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
        `--remote-debugging-port=${debugPort}`,
        `--user-data-dir=${join(temp, "profile")}`,
        "about:blank",
      ],
      { stdio: "ignore" },
    ),
  );
  const page = await eventually(async () => {
    const pages = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
    return pages.find((page) => page.type === "page");
  }, "headless Chrome");
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = reject;
  });
  const pending = new Map();
  const exceptions = [];
  let id = 0;
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const entry = pending.get(message.id);
      if (entry) {
        pending.delete(message.id);
        message.error
          ? entry.reject(new Error(JSON.stringify(message.error)))
          : entry.resolve(message.result);
      }
    } else if (message.method === "Runtime.exceptionThrown")
      exceptions.push(message.params.exceptionDetails.text);
  };
  const cdp = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const requestId = ++id;
      pending.set(requestId, { resolve, reject });
      socket.send(JSON.stringify({ id: requestId, method, params }));
    });
  const evaluate = async (expression) => {
    const result = await cdp("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const text = () => evaluate("document.body.innerText");
  await cdp("Page.enable");
  await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 800,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp("Page.navigate", { url: `http://127.0.0.1:${vitePort}/demo` });
  await eventually(
    async () => (await text()).includes("No reconstruction job yet."),
    "empty verified UI",
  );
  assert.equal(await evaluate("document.querySelectorAll('canvas').length"), 0);
  assert.ok(
    !requests.some((url) => url.includes("/static/")),
    "empty manifest must not load old static assets",
  );

  const video = join(temp, "browser-fixture.mp4");
  writeFileSync(video, "fixture transport bytes; not an actual reconstruction video");
  const documentNode = await cdp("DOM.getDocument");
  const input = await cdp("DOM.querySelector", {
    nodeId: documentNode.root.nodeId,
    selector: "input[type=file]",
  });
  await cdp("DOM.setFileInputFiles", { nodeId: input.nodeId, files: [video] });
  await eventually(
    async () => (await text()).includes("browser-job") && (await text()).includes("PROCESSING"),
    "accepted local upload status",
  );
  await cdp("Page.reload");
  await eventually(
    async () => (await text()).includes("browser-job") && (await text()).includes("PROCESSING"),
    "durable job after reload",
  );
  currentStatus = status("error", "browser-job");
  await eventually(
    async () => (await text()).includes("Reconstruction failed: Geometry verification failed"),
    "persistent pipeline failure",
  );
  await sleep(2300);
  assert.ok((await text()).includes("Reconstruction failed: Geometry verification failed"));
  assert.equal(await evaluate("document.querySelectorAll('canvas').length"), 0);

  currentStatus = status("completed", "browser-job");
  currentScene = { status: "ready", manifest: { ...manifest("browser-job"), gaussian_count: 3 } };
  await eventually(
    async () =>
      (await text()).includes("3 learned Gaussians") &&
      (await evaluate("document.querySelectorAll('canvas').length === 1")),
    "versioned Gaussian renderer",
  );
  await sleep(1000);
  assert.ok(!(await text()).includes("Viewer error"));
  const screenshot = await cdp("Page.captureScreenshot", { format: "png" });
  const imagePath = join(temp, "verified-gaussian-quads.png");
  writeFileSync(imagePath, Buffer.from(screenshot.data, "base64"));
  // Inspect actual screenshot pixels from the central viewport, not the UI labels.
  const pixels = await evaluate(`(async () => {
    const image = new Image(); image.src = 'data:image/png;base64,${screenshot.data}'; await image.decode();
    const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
    const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, 0);
    const bytes = ctx.getImageData(350, 100, 880, 580).data;
    const bounds = Array.from({ length: 3 }, () => ({ count: 0, minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity, peak: 0 }));
    for (let i = 0; i < bytes.length; i += 4) {
      for (let c = 0; c < 3; c++) {
        if (bytes[i+c] > 40 && bytes[i+c] > bytes[i+(c+1)%3] * 2 && bytes[i+c] > bytes[i+(c+2)%3] * 2) {
          const b = bounds[c], x = (i / 4) % 880, y = Math.floor(i / 4 / 880);
          b.count++; b.minX = Math.min(b.minX, x); b.maxX = Math.max(b.maxX, x);
          b.minY = Math.min(b.minY, y); b.maxY = Math.max(b.maxY, y); b.peak = Math.max(b.peak, bytes[i+c]);
        }
      }
    }
    return bounds.map((b) => ({ count: b.count, width: b.maxX-b.minX+1, height: b.maxY-b.minY+1, peak: b.peak }));
  })()`);
  assert.ok(
    pixels.every((color) => color.count > 100 && color.peak > 100 && color.peak < 225),
    `Actual Gaussian pixels missing: ${JSON.stringify(pixels)}`,
  );
  assert.ok(
    pixels[0].width > pixels[0].height * 4 && pixels[2].width > pixels[2].height * 4,
    "X scale must produce horizontal Gaussians",
  );
  assert.ok(
    pixels[1].height > pixels[1].width * 4,
    "WXYZ rotation must produce the vertical Gaussian",
  );
  currentStatus = status("error", "later-failed-job");
  await eventually(
    async () =>
      (await text()).includes("Previous verified scene") &&
      (await text()).includes("later-failed-job"),
    "previous successful scene on later failure",
  );
  assert.equal(await evaluate("document.querySelectorAll('canvas').length"), 1);
  assert.ok(
    requests.every(
      (url) => !/\/api\/objects|\/api\/query|\/api\/edit|kaggle|\/static\/scene\./.test(url),
    ),
    "verified UI must never call legacy data paths",
  );
  assert.deepEqual(exceptions, []);
  console.log(
    JSON.stringify(
      {
        result: "PASS",
        checks: [
          "empty UI",
          "local upload",
          "durable processing after reload",
          "persistent failure",
          "versioned WebGL anisotropic quads",
          "previous scene preserved",
          "no legacy endpoints",
        ],
        pixels,
        screenshot: imagePath,
      },
      null,
      2,
    ),
  );
} finally {
  if (socket) socket.close();
  for (const child of children.reverse()) {
    if (process.platform === "win32")
      spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    else child.kill("SIGTERM");
  }
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
  // Leave only the diagnostic PNG in the temp directory. Profile deletion may need a brief shutdown delay.
  await sleep(1000);
  rmSync(join(temp, "profile"), { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  rmSync(join(temp, "browser-fixture.mp4"), { force: true });
}
