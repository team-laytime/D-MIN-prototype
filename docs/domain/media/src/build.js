// node build.js v1 [--sheet]  → out/v1.mp4 (or out/v1-sheet/*.png)
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const { execFileSync, spawn } = require('child_process');
const puppeteer = require('puppeteer-core');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const [, , vid, ...flags] = process.argv;
if (!vid) { console.error('usage: node build.js v1|v2|v3|v4 [--sheet]'); process.exit(1); }
const SHEET = flags.includes('--sheet'), FPS = 30, W = 1280, H = 720, LEAD = 0.6, TAIL = 1.0;
const root = __dirname, out = path.join(root, 'out'), ttsDir = path.join(root, 'tts');
fs.mkdirSync(out, { recursive: true }); fs.mkdirSync(ttsDir, { recursive: true });
const script = JSON.parse(fs.readFileSync(path.join(root, 'scripts', vid + '.json'), 'utf8'));

// 1) TTS per scene (cached by text hash) and timeline
let t = 0; const timeline = [];
for (const sc of script.scenes) {
  const h = crypto.createHash('md5').update(`${script.voice}|${script.rate}|${sc.tts}`).digest('hex').slice(0, 12);
  const aiff = path.join(ttsDir, `${h}.aiff`), wav = path.join(ttsDir, `${h}.wav`);
  if (!fs.existsSync(wav)) {
    execFileSync('say', ['-v', script.voice, '-r', String(script.rate), '-o', aiff, sc.tts]);
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', aiff, '-ar', '44100', '-ac', '1', wav]);
  }
  const adur = parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', wav]).toString());
  const dur = Math.max(sc.minDur || 0, LEAD + adur + TAIL);
  timeline.push({ id: sc.id, caption: sc.caption, start: +t.toFixed(3), dur: +dur.toFixed(3), audio: wav, audioStart: +(t + LEAD).toFixed(3), adur: +adur.toFixed(3) });
  t += dur;
}
const total = +t.toFixed(3);
fs.writeFileSync(path.join(out, vid + '-timeline.json'), JSON.stringify({ total, timeline }, null, 1));
console.log(`${vid}: ${timeline.length} scenes, total ${total}s`); timeline.forEach(s => console.log(`  ${s.id.padEnd(10)} start ${String(s.start).padStart(7)}  dur ${String(s.dur).padStart(6)}  tts ${s.adur}`));

// 2) audio mix: silence base + each narration delayed to its scene start
const audioOut = path.join(out, vid + '-audio.wav');
{
  const inputs = [], filters = [];
  timeline.forEach((s, i) => { inputs.push('-i', s.audio); filters.push(`[${i + 1}]adelay=${Math.round(s.audioStart * 1000)}:all=1[a${i}]`); });
  const mix = `[0]${timeline.map((_, i) => `[a${i}]`).join('')}amix=inputs=${timeline.length + 1}:duration=first:normalize=0[out]`;
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-t', String(total), '-i', 'anullsrc=r=44100:cl=mono', ...inputs, '-filter_complex', filters.join(';') + ';' + mix, '-map', '[out]', audioOut]);
}

// 3) frames
(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox', '--allow-file-access-from-files', '--hide-scrollbars', '--force-device-scale-factor=1', '--font-render-hinting=none', '--disable-gpu', '--lang=ko-KR'] });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('PAGE ERROR:', e.message));
  page.on('console', m => { if (m.type() === 'error') console.error('CONSOLE:', m.text()); });
  await page.goto('file://' + path.join(root, vid + '.html'), { waitUntil: 'networkidle0', timeout: 60000 });
  await page.evaluate(tl => window.__setTimeline(tl), timeline.map(({ id, caption, start, dur }) => ({ id, caption, start, dur })));
  await page.evaluate(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 400));
  if (SHEET) {
    const dir = path.join(out, vid + '-sheet'); fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
    let idx = 0;
    for (const s of timeline) for (const f of [0.12, 0.55, 0.92]) {
      const tt = s.start + s.dur * f; await page.evaluate(t => window.__render(t), tt);
      await page.screenshot({ path: path.join(dir, `${String(idx++).padStart(2, '0')}-${s.id}-${Math.round(f * 100)}.png`), type: 'png' });
    }
    await browser.close(); console.log('sheet →', dir); return;
  }
  const nFrames = Math.ceil(total * FPS);
  const mp4 = path.join(out, vid + '.mp4');
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-', '-i', audioOut, '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', mp4], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = 0; i < nFrames; i++) {
    await page.evaluate(t => window.__render(t), i / FPS);
    const buf = await page.screenshot({ type: 'png' });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 450 === 0) console.log(`  frame ${i}/${nFrames}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); await browser.close();
  console.log(`done → ${mp4}  (${total}s, ${nFrames} frames, ${((Date.now() - t0) / 1000).toFixed(0)}s render)`);
})().catch(e => { console.error(e); process.exit(1); });
