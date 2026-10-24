// Feature benchmark: drives the real pages in Chromium against a fake YouTube and
// checks each feature youtubetotranscript.com offers. Run: node tests/benchmark.js
const { spawn } = require("child_process");
const path = require("path");
const { chromium } = require("playwright");

const PORT = 5077;
const BASE = `http://127.0.0.1:${PORT}`;
const ID = "dQw4w9WgXcQ";

// A stand-in for YouTube's player API, so syncing can be tested offline.
const FAKE_YT = `
  window.__seeks = [];
  window.YT = { Player: function (el, opts) {
    this.t = 0;
    this.getCurrentTime = () => this.t;
    this.getPlayerState = () => 1;
    this.seekTo = (s) => { this.t = s; window.__seeks.push(s); };
    this.playVideo = () => {};
    window.__player = this;
  } };
  setTimeout(() => window.onYouTubeIframeAPIReady && window.onYouTubeIframeAPIReady(), 0);
`;

const results = [];
async function check(name, fn) {
  try { await fn(); results.push([name, true, ""]); }
  catch (e) { results.push([name, false, e.message.split("\n")[0]]); }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }

(async () => {
  const server = spawn("python3", [path.join(__dirname, "stub_server.py"), String(PORT)], { stdio: "ignore" });
  for (let i = 0; i < 50; i++) {
    try { await fetch(BASE + "/"); break; } catch { await new Promise((r) => setTimeout(r, 200)); }
  }

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ permissions: ["clipboard-read", "clipboard-write"] });
  await ctx.route("https://www.youtube.com/iframe_api", (r) => r.fulfill({ contentType: "text/javascript", body: FAKE_YT }));
  await ctx.route(/fonts\.(googleapis|gstatic)\.com|i\.ytimg\.com/, (r) => r.abort());
  const page = await ctx.newPage();

  await check("Paste a link on the home page opens the transcript", async () => {
    await page.goto(BASE + "/");
    await page.fill("#url", `https://youtu.be/${ID}?si=x`);
    await page.click("#go");
    await page.waitForURL(`**/transcript?v=${ID}`);
    await page.waitForSelector(".line");
  });

  await check("Pasting a link starts without pressing the button", async () => {
    await page.goto(BASE + "/");
    await page.focus("#url");
    await page.evaluate((id) => {
      const el = document.getElementById("url");
      el.value = "https://www.youtube.com/watch?v=" + id;
      el.dispatchEvent(new Event("paste"));
    }, ID);
    await page.waitForURL(`**/transcript?v=${ID}`);
  });

  await check("Shorts, live and embed links all work", async () => {
    for (const p of [`/shorts/${ID}`, `/live/${ID}`, `/watch?v=${ID}`]) {
      await page.goto(BASE + p);
      await page.waitForSelector(".line");
    }
  });

  await check("Bad link shows a clear error", async () => {
    await page.goto(BASE + "/");
    await page.fill("#url", "hello");
    await page.click("#go");
    assert(await page.isVisible("#error"), "error not shown");
  });

  await page.goto(`${BASE}/transcript?v=${ID}`);
  await page.waitForSelector(".line");

  await check("Shows title, channel, word count and full transcript", async () => {
    assert((await page.textContent("#vtitle")) === "Test video", "title");
    assert((await page.textContent("#vauthor")) === "Test channel", "channel");
    assert((await page.locator(".line").count()) === 6, "line count");
    assert(/\d+ words/.test(await page.textContent("#status")), "word count");
  });

  await check("Line being spoken is highlighted (follows the video)", async () => {
    await page.evaluate(() => { window.__player.t = 10; });
    await page.waitForFunction(() => document.querySelector(".line.active")?.dataset.start === "9");
  });

  await check("Clicking a line jumps the video there", async () => {
    await page.locator(".line").nth(3).click();
    const seeks = await page.evaluate(() => window.__seeks);
    assert(seeks.at(-1) === 13.5, "seek " + seeks);
  });

  await check("Timestamps can be turned off and on", async () => {
    await page.click("#times");
    assert(!(await page.isVisible(".line time")), "times still visible");
    await page.click("#times");
    assert(await page.isVisible(".line time"), "times hidden");
  });

  await check("Paragraph view", async () => {
    await page.click("#para");
    assert((await page.locator(".line").count()) < 6, "not grouped");
    await page.click("#para");
  });

  await check("Search highlights matches", async () => {
    await page.fill("#search", "x-men");
    assert((await page.locator(".line").count()) === 1, "filter");
    assert((await page.locator("mark").first().textContent()) === "X-Men", "mark");
    assert((await page.textContent("#status")).startsWith("1 match"), "status");
    await page.fill("#search", "");
  });

  await check("Copy puts the transcript on the clipboard", async () => {
    await page.click("#copy");
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    assert(clip.startsWith("[0:00] Welcome back"), clip.slice(0, 40));
  });

  for (const [id, fmt, expect] of [["dl-txt", "txt", "Welcome back"], ["dl-txt-times", "txt", "[0:00]"], ["dl-srt", "srt", "1\n00:00:00,000"], ["dl-vtt", "vtt", "WEBVTT"]]) {
    await check(`Download ${id.replace("dl-", "")}`, async () => {
      await page.click("#dl");
      const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#" + id)]);
      assert(dl.suggestedFilename() === `transcript-${ID}.${fmt}`, dl.suggestedFilename());
      const body = require("fs").readFileSync(await dl.path(), "utf8");
      assert(body.startsWith(expect), body.slice(0, 30));
    });
  }

  await check("Switch caption language", async () => {
    await page.selectOption("#lang", "es");
    await page.waitForFunction(() => document.querySelector(".line p").textContent.startsWith("[es]"));
    assert(page.url().includes("lang=es"), "url not updated");
  });

  await check("Translate into another language", async () => {
    await page.selectOption("#lang", "fr");
    await page.waitForFunction(() => document.querySelector(".line p").textContent.startsWith("[fr]"));
    assert((await page.textContent("#status")).includes("translated"), "status");
  });

  await check("AI summary", async () => {
    await page.click("#summarize");
    await page.waitForFunction(() => document.getElementById("summary").textContent.includes("Key points"));
  });

  await check("No-captions video shows a clear message", async () => {
    await page.goto(`${BASE}/transcript?v=nocaptions0`);
    await page.waitForSelector("#lines .error");
    assert((await page.textContent("#lines")).includes("no captions"), "message");
  });

  await check("Recently opened videos on the home page", async () => {
    await page.goto(BASE + "/");
    assert(await page.isVisible("#recent-card"), "not shown");
    assert((await page.textContent("#recent")).includes("Test video"), "title missing");
  });

  await check("Phone width: no sideways scrolling", async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const p of ["/", `/transcript?v=${ID}`]) {
      await page.goto(BASE + p);
      await page.waitForLoadState("networkidle");
      const wide = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      assert(!wide, p + " scrolls sideways");
    }
  });

  await page.screenshot({ path: process.env.SHOT || "/dev/null" }).catch(() => {});
  await browser.close();
  server.kill();

  const passed = results.filter((r) => r[1]).length;
  for (const [name, ok, why] of results) console.log(`${ok ? "PASS" : "FAIL"}  ${name}${why ? "  — " + why : ""}`);
  console.log(`\n${passed}/${results.length} features passing`);
  process.exit(passed === results.length ? 0 : 1);
})();
