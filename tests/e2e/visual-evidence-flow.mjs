import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";


const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const extensionPath = path.join(root, "extensions", "psos-visual-evidence");
const serverPath = path.join(root, "tests", "fixtures", "visual_evidence_e2e_server.py");
const runId = "psos-visual-e2e";
const baseUrl = "http://127.0.0.1:8765";


function assert(condition, message) {
  if (!condition) throw new Error(message);
}


function waitForServer(server) {
  return new Promise((resolve, reject) => {
    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      reject(new Error(`E2E fixture server did not start.\nstdout:\n${stdout}\nstderr:\n${stderr}`));
    }, 20_000);

    server.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
      if (stdout.includes("READY ")) {
        clearTimeout(timeout);
        resolve({ stdout: () => stdout, stderr: () => stderr });
      }
    });
    server.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    server.once("exit", (code) => {
      clearTimeout(timeout);
      reject(new Error(`E2E fixture server exited early (${code}).\nstderr:\n${stderr}`));
    });
  });
}


async function waitForServiceWorker(context) {
  const existing = context.serviceWorkers()[0];
  if (existing) return existing;
  return context.waitForEvent("serviceworker", { timeout: 15_000 });
}


async function run() {
  const tempRoot = await mkdtemp(path.join(os.tmpdir(), "psos-visual-e2e-"));
  const runDir = path.join(tempRoot, "run");
  const userDataDir = path.join(tempRoot, "chromium-profile");
  const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
  const server = spawn(python, ["-B", serverPath, "--run-dir", runDir], {
    cwd: root,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });

  let context = null;
  let page = null;
  let serverOutput = null;
  try {
    serverOutput = await waitForServer(server);
    context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      args: [
        `--disable-extensions-except=${extensionPath}`,
        `--load-extension=${extensionPath}`,
        "--no-first-run",
        "--disable-default-apps",
      ],
    });
    page = context.pages()[0] || (await context.newPage());
    await page.goto(`${baseUrl}/shop`, { waitUntil: "networkidle" });
    await page.waitForFunction(() => {
      const image = document.querySelector("#review-photo");
      return image instanceof HTMLImageElement && image.complete && image.naturalWidth === 640;
    });

    const serviceWorker = await waitForServiceWorker(context);
    await serviceWorker.evaluate(
      async ({ runId: targetRunId }) => {
        const tabs = await chrome.tabs.query({});
        const tab = tabs.find((item) => item.url?.includes("/shop"));
        if (!tab?.id) throw new Error("shop tab not found");
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["content.js"],
        });
        await chrome.tabs.sendMessage(tab.id, {
          type: "PSOS_VISUAL_PICKER_OPEN",
          defaults: {
            runId: targetRunId,
            subjectLabel: "후보 A",
            sourceKind: "buyer_review",
          },
        });
      },
      { runId },
    );

    const picker = page.locator("#psos-visual-evidence-host");
    await picker.waitFor({ state: "attached", timeout: 10_000 });
    const checkboxes = picker.locator('input[type="checkbox"]');
    const candidateCount = await checkboxes.count();
    assert(candidateCount === 1, `expected one eligible image, found ${candidateCount}`);
    assert((await picker.locator("#run-id").inputValue()) === runId, "run ID default was not restored");
    assert(
      (await picker.locator("#subject-label").inputValue()) === "후보 A",
      "candidate default was not restored",
    );
    assert(
      (await picker.locator("#source-kind").inputValue()) === "buyer_review",
      "source kind default was not restored",
    );

    await checkboxes.first().check();
    await picker.locator("#submit").click();
    await picker
      .locator("#status")
      .filter({ hasText: "사진 1장을 추가했습니다" })
      .waitFor({ state: "visible", timeout: 15_000 });

    await page.goto(`${baseUrl}/review`, { waitUntil: "networkidle" });
    const panel = page.locator("#quality-evidence-review");
    await panel.waitFor({ state: "visible", timeout: 10_000 });
    const importedCard = panel.locator(".quality-card").filter({ hasText: "후보 A" });
    await importedCard.waitFor({ state: "visible", timeout: 10_000 });
    const cardText = await importedCard.textContent();
    assert(cardText?.includes("로컬 보존"), "review card does not expose local archive metadata");
    const previewSource = await importedCard.locator("img").getAttribute("src");
    assert(
      previewSource?.includes(`/api/runs/${runId}/evidence-items/`),
      `expected local evidence preview endpoint, got ${previewSource}`,
    );

    const bundle = JSON.parse(await readFile(path.join(runDir, "evidence_bundle.json"), "utf8"));
    const imported = bundle.items.find((item) => item.capture?.source_kind === "buyer_review");
    assert(imported, "imported visual evidence item was not saved");
    assert(imported.subject_id?.startsWith("candidate-"), "candidate subject was not linked explicitly");
    assert(imported.archive?.status === "archived", "image was not archived locally");
    assert(
      imported.archive?.original_url === `${baseUrl}/images/review.png`,
      "original image URL was not preserved",
    );
    assert(imported.integrity?.sha256 === imported.archive?.sha256, "archive integrity hash mismatch");
    assert(existsSync(path.join(runDir, imported.source)), "archived image file does not exist");

    const history = JSON.parse(
      await readFile(path.join(runDir, "visual_evidence_imports.json"), "utf8"),
    );
    assert(history.imports.length === 1, "visual import history was not written once");
    assert(
      history.imports[0].archived_item_ids.includes(imported.id),
      "archived item was not anchored in import history",
    );

    console.log("PASS visual evidence extension → archive → review gallery");
  } catch (error) {
    if (page) {
      await page.screenshot({ path: path.join(root, "visual-evidence-e2e-failure.png"), fullPage: true }).catch(() => {});
    }
    const diagnostics = serverOutput
      ? `\nserver stdout:\n${serverOutput.stdout()}\nserver stderr:\n${serverOutput.stderr()}`
      : "";
    throw new Error(`${error.stack || error}${diagnostics}`);
  } finally {
    await context?.close().catch(() => {});
    if (!server.killed) server.kill();
    await rm(tempRoot, { recursive: true, force: true });
  }
}


await run();
