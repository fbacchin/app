"use strict";
/* ============================================================
   ASSALTO ALLA MORTE NERA
   Fan game arcade ispirato a Guerre Stellari.
   Grafica vettoriale disegnata su canvas, audio sintetizzato
   con WebAudio: nessuna risorsa esterna.
   ============================================================ */

// ---------------------------------------------------------- canvas
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");
let W = 0, H = 0, DPR = 1, MINWH = 0;

function resize() {
  DPR = Math.min(window.devicePixelRatio || 1, 2);
  W = window.innerWidth;
  H = window.innerHeight;
  MINWH = Math.min(W, H);
  canvas.width = Math.round(W * DPR);
  canvas.height = Math.round(H * DPR);
  canvas.style.width = W + "px";
  canvas.style.height = H + "px";
}
window.addEventListener("resize", resize);
resize();

// ---------------------------------------------------------- utilità
const TAU = Math.PI * 2;
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const lerp = (a, b, t) => a + (b - a) * t;
const rand = (a, b) => a + Math.random() * (b - a);
const dist2 = (ax, ay, bx, by) => {
  const dx = ax - bx, dy = ay - by;
  return dx * dx + dy * dy;
};

function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function poly(pts) {
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.closePath();
}

function text(str, x, y, size, color, align, bold) {
  ctx.fillStyle = color;
  ctx.font = (bold ? "bold " : "") + size + "px 'Courier New', monospace";
  ctx.textAlign = align || "center";
  ctx.textBaseline = "middle";
  ctx.fillText(str, x, y);
}

const fmtScore = (n) => String(Math.max(0, Math.floor(n))).padStart(6, "0");

// ---------------------------------------------------------- audio (WebAudio sintetizzato)
const AudioFX = {
  ctx: null, master: null, muted: false, noiseBuf: null, humOsc: null, humGain: null,

  init() {
    try {
      if (!this.ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        this.ctx = new AC();
        this.master = this.ctx.createGain();
        this.master.gain.value = this.muted ? 0 : 0.5;
        this.master.connect(this.ctx.destination);
        const len = Math.floor(this.ctx.sampleRate * 1.2);
        this.noiseBuf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
        const d = this.noiseBuf.getChannelData(0);
        for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
      }
      if (this.ctx.state === "suspended") this.ctx.resume();
    } catch (e) { /* niente audio, il gioco continua */ }
  },

  setMuted(m) {
    this.muted = m;
    if (this.master) this.master.gain.value = m ? 0 : 0.5;
  },

  blip(f0, f1, dur, type, vol) {
    if (!this.ctx) return;
    try {
      const t = this.ctx.currentTime;
      const o = this.ctx.createOscillator();
      const g = this.ctx.createGain();
      o.type = type;
      o.frequency.setValueAtTime(f0, t);
      o.frequency.exponentialRampToValueAtTime(Math.max(1, f1), t + dur);
      g.gain.setValueAtTime(vol, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + dur);
      o.connect(g); g.connect(this.master);
      o.start(t); o.stop(t + dur + 0.02);
    } catch (e) {}
  },

  noise(dur, vol, f0, f1) {
    if (!this.ctx) return;
    try {
      const t = this.ctx.currentTime;
      const src = this.ctx.createBufferSource();
      src.buffer = this.noiseBuf; src.loop = true;
      const flt = this.ctx.createBiquadFilter();
      flt.type = "lowpass";
      flt.frequency.setValueAtTime(f0, t);
      flt.frequency.exponentialRampToValueAtTime(Math.max(40, f1), t + dur);
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(vol, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + dur);
      src.connect(flt); flt.connect(g); g.connect(this.master);
      src.start(t); src.stop(t + dur + 0.05);
    } catch (e) {}
  },

  laser()      { this.blip(1500, 320, 0.11, "sawtooth", 0.16); },
  enemyLaser() { this.blip(760, 190, 0.16, "square", 0.10); },
  boom()       { this.noise(0.5, 0.5, 2400, 120); this.blip(220, 40, 0.4, "triangle", 0.25); },
  hit()        { this.blip(300, 70, 0.25, "triangle", 0.3); this.noise(0.2, 0.25, 1600, 300); },
  torpedo()    { this.blip(180, 70, 0.6, "sine", 0.3); this.noise(0.45, 0.12, 900, 200); },
  lock()       { this.blip(880, 880, 0.07, "square", 0.12); },
  warn()       { this.blip(520, 300, 0.09, "square", 0.09); },
  wave()       { this.blip(440, 660, 0.18, "square", 0.14); },
  bigBoom() {
    this.noise(2.8, 0.8, 3200, 60);
    this.blip(120, 24, 2.2, "sine", 0.5);
    this.blip(90, 30, 2.6, "triangle", 0.3);
  },

  humStart() {
    if (!this.ctx || this.humOsc) return;
    try {
      this.humOsc = this.ctx.createOscillator();
      this.humGain = this.ctx.createGain();
      this.humOsc.type = "sawtooth";
      this.humOsc.frequency.value = 52;
      this.humGain.gain.value = 0.028;
      this.humOsc.connect(this.humGain); this.humGain.connect(this.master);
      this.humOsc.start();
    } catch (e) { this.humOsc = null; }
  },
  humStop() {
    try { if (this.humOsc) { this.humOsc.stop(); } } catch (e) {}
    this.humOsc = null; this.humGain = null;
  },
};

// ---------------------------------------------------------- input
const keys = {};
const pressedCodes = new Set();
let touchTapped = false;
let hasTouch = false;

const GAME_KEYS = ["Space", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];

window.addEventListener("keydown", (e) => {
  if (GAME_KEYS.includes(e.code)) e.preventDefault();
  AudioFX.init();
  if (!e.repeat) {
    pressedCodes.add(e.code);
    if (e.code === "KeyM") AudioFX.setMuted(!AudioFX.muted);
  }
  keys[e.code] = true;
});
window.addEventListener("keyup", (e) => { keys[e.code] = false; });
window.addEventListener("blur", () => {
  for (const k in keys) keys[k] = false;
  if (G.screen === "space" || G.screen === "trench") G.paused = true;
});

const popKey = (code) => (pressedCodes.has(code) ? (pressedCodes.delete(code), true) : false);
const anyStartPressed = () => {
  const p = popKey("Enter") || popKey("Space") || touchTapped;
  touchTapped = false;
  return p;
};

// Touch: trascina a sinistra per muoverti, pulsanti a destra per sparare.
const touchState = { moveId: null, mx: 0, my: 0, fireId: null, torpId: null };
const fireBtn = () => ({ x: W - 74, y: H - 88, r: 46 });
const torpBtn = () => ({ x: W - 74, y: H - 205, r: 40 });

function inCircle(x, y, c) { return dist2(x, y, c.x, c.y) < c.r * c.r; }

canvas.addEventListener("touchstart", (e) => {
  e.preventDefault();
  hasTouch = true;
  AudioFX.init();
  if (G.paused || G.screen === "title" || G.screen === "crawl" ||
      G.screen === "victory" || G.screen === "gameover") {
    touchTapped = true;
  }
  for (const t of e.changedTouches) {
    if (inCircle(t.clientX, t.clientY, fireBtn())) touchState.fireId = t.identifier;
    else if (G.screen === "trench" && inCircle(t.clientX, t.clientY, torpBtn())) {
      touchState.torpId = t.identifier;
      pressedCodes.add("KeyX");
    } else if (t.clientX < W * 0.62 && touchState.moveId === null) {
      touchState.moveId = t.identifier;
      touchState.mx = t.clientX; touchState.my = t.clientY;
    } else touchState.fireId = t.identifier;
  }
}, { passive: false });

canvas.addEventListener("touchmove", (e) => {
  e.preventDefault();
  for (const t of e.changedTouches) {
    if (t.identifier === touchState.moveId) {
      const dx = t.clientX - touchState.mx;
      const dy = t.clientY - touchState.my;
      touchState.mx = t.clientX; touchState.my = t.clientY;
      onTouchDrag(dx, dy);
    }
  }
}, { passive: false });

function touchEnd(e) {
  e.preventDefault();
  for (const t of e.changedTouches) {
    if (t.identifier === touchState.moveId) touchState.moveId = null;
    if (t.identifier === touchState.fireId) touchState.fireId = null;
    if (t.identifier === touchState.torpId) touchState.torpId = null;
  }
}
canvas.addEventListener("touchend", touchEnd, { passive: false });
canvas.addEventListener("touchcancel", touchEnd, { passive: false });

// Un click del mouse equivale a INVIO nelle schermate di menu (e sblocca l'audio).
canvas.addEventListener("mousedown", () => {
  AudioFX.init();
  if (G.paused || G.screen === "title" || G.screen === "crawl" ||
      G.screen === "victory" || G.screen === "gameover") {
    touchTapped = true;
  }
});

function onTouchDrag(dx, dy) {
  if (G.screen === "space" && space) {
    space.player.x = clamp(space.player.x + dx * 1.5, 22, W - 22);
    space.player.y = clamp(space.player.y + dy * 1.5, H * 0.35, H - 34);
  } else if (G.screen === "trench" && trench) {
    trench.ship.x = clamp(trench.ship.x + dx * 0.005, -0.8, 0.8);
    trench.ship.y = clamp(trench.ship.y - dy * 0.005, 0.08, 1.12);
  }
}

const fireHeld = () => keys["Space"] || touchState.fireId !== null;

// ---------------------------------------------------------- stato globale
const G = {
  screen: "title",       // title | crawl | space | approach | trench | vseq | victory | gameover
  score: 0,
  hi: 0,
  paused: false,
  shake: 0,
  msg: null, msgT: 0, msgDur: 1,
  overReason: "",
  spaceStartScore: 0,
  trenchStartScore: 0,
  diedIn: "space",
  time: 0,
};

try { G.hi = parseInt(localStorage.getItem("mortenera-hi") || "0", 10) || 0; } catch (e) {}
function saveHi() {
  if (G.score > G.hi) {
    G.hi = G.score;
    try { localStorage.setItem("mortenera-hi", String(G.hi)); } catch (e) {}
  }
}

function showMsg(m, dur) {
  G.msg = m; G.msgDur = dur || 2.2; G.msgT = G.msgDur;
}

// ---------------------------------------------------------- campo stellare
let stars = [];
function makeStars() {
  stars = [];
  const n = Math.floor((W * H) / 4200);
  for (let i = 0; i < n; i++) {
    stars.push({ x: Math.random(), y: Math.random(), z: rand(0.25, 1), tw: rand(0, TAU) });
  }
}
makeStars();
window.addEventListener("resize", makeStars);

function drawStars(scrollY, speedMul) {
  for (const s of stars) {
    const sy = ((s.y + scrollY * s.z * (speedMul || 1)) % 1 + 1) % 1;
    const a = 0.35 + 0.65 * s.z * (0.75 + 0.25 * Math.sin(G.time * 2 + s.tw));
    ctx.fillStyle = "rgba(255,255,255," + a.toFixed(3) + ")";
    const sz = s.z > 0.8 ? 2 : 1;
    ctx.fillRect(s.x * W, sy * H, sz, sz);
  }
}

// ---------------------------------------------------------- Morte Nera
const dsFeatures = (() => {
  const rng = mulberry32(20771977);
  const out = [];
  for (let i = 0; i < 150; i++) {
    let x, y;
    do { x = rng() * 2 - 1; y = rng() * 2 - 1; } while (x * x + y * y > 0.92);
    out.push({ x, y, w: 0.015 + rng() * 0.05, h: 0.008 + rng() * 0.03, a: 0.08 + rng() * 0.2 });
  }
  return out;
})();

function drawDeathStar(x, y, r, alpha, dmg) {
  if (r < 2 || alpha <= 0) return;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.translate(x, y);

  const g = ctx.createRadialGradient(-r * 0.4, -r * 0.4, r * 0.1, 0, 0, r * 1.05);
  g.addColorStop(0, "#aeb6c2");
  g.addColorStop(0.55, "#767f8d");
  g.addColorStop(1, "#3a414c");
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(0, 0, r, 0, TAU); ctx.fill();

  ctx.save();
  ctx.beginPath(); ctx.arc(0, 0, r, 0, TAU); ctx.clip();

  // pannellature superficiali
  for (const f of dsFeatures) {
    ctx.fillStyle = "rgba(20,24,32," + f.a.toFixed(3) + ")";
    ctx.fillRect(f.x * r, f.y * r, Math.max(1, f.w * r), Math.max(1, f.h * r));
  }
  // trincea equatoriale
  ctx.fillStyle = "rgba(18,22,30,0.85)";
  ctx.fillRect(-r, r * 0.02, 2 * r, Math.max(2, r * 0.07));
  ctx.fillStyle = "rgba(150,160,175,0.25)";
  ctx.fillRect(-r, r * 0.015, 2 * r, 1.5);

  // superlaser
  const dx = -r * 0.38, dy = -r * 0.32, dr = r * 0.235;
  const dg = ctx.createRadialGradient(dx - dr * 0.3, dy - dr * 0.3, dr * 0.1, dx, dy, dr);
  dg.addColorStop(0, "#4d5560");
  dg.addColorStop(1, "#2a3039");
  ctx.fillStyle = dg;
  ctx.beginPath(); ctx.arc(dx, dy, dr, 0, TAU); ctx.fill();
  ctx.strokeStyle = "rgba(190,200,215,0.5)";
  ctx.lineWidth = Math.max(1, r * 0.008);
  ctx.beginPath(); ctx.arc(dx, dy, dr, 0, TAU); ctx.stroke();
  ctx.beginPath(); ctx.arc(dx, dy, dr * 0.55, 0, TAU); ctx.stroke();
  ctx.fillStyle = "rgba(200,210,225,0.7)";
  ctx.beginPath(); ctx.arc(dx, dy, Math.max(1.2, dr * 0.09), 0, TAU); ctx.fill();

  // ombra del terminatore
  const sh = ctx.createRadialGradient(r * 0.55, r * 0.55, r * 0.2, 0, 0, r * 1.25);
  sh.addColorStop(0, "rgba(0,0,0,0.55)");
  sh.addColorStop(0.5, "rgba(0,0,0,0.12)");
  sh.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = sh;
  ctx.fillRect(-r, -r, 2 * r, 2 * r);

  // lampi di danno durante l'esplosione finale
  if (dmg > 0) {
    ctx.strokeStyle = "rgba(255,240,180," + Math.min(1, dmg).toFixed(2) + ")";
    ctx.lineWidth = Math.max(1.5, r * 0.012);
    const rng = mulberry32(77);
    for (let i = 0; i < 7; i++) {
      const a0 = rng() * TAU;
      ctx.beginPath();
      let px = Math.cos(a0) * r * 0.15, py = Math.sin(a0) * r * 0.15;
      ctx.moveTo(px, py);
      for (let k = 0; k < 5; k++) {
        px += (rng() - 0.5) * r * 0.5; py += (rng() - 0.5) * r * 0.5;
        ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
  }
  ctx.restore();

  ctx.strokeStyle = "rgba(160,170,185,0.35)";
  ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(0, 0, r, 0, TAU); ctx.stroke();
  ctx.restore();
}

// ---------------------------------------------------------- disegno navi
function drawPlayerTop(x, y, vx, flick) {
  ctx.save();
  ctx.translate(x, y);
  const b = clamp(vx / 380, -1, 1);
  ctx.rotate(b * 0.14);
  ctx.scale(1 - Math.abs(b) * 0.12, 1);

  // motori
  const fl = 8 + Math.random() * 7;
  ctx.fillStyle = "rgba(120,190,255,0.8)";
  poly([[-7, 15], [-3.5, 15], [-5.2, 15 + fl]]); ctx.fill();
  poly([[7, 15], [3.5, 15], [5.2, 15 + fl]]); ctx.fill();

  // ali (doppie, stile S-foil)
  ctx.fillStyle = "#9aa1b4";
  poly([[-3, 1], [-24, -6], [-24, -2], [-3, 6]]); ctx.fill();
  poly([[3, 1], [24, -6], [24, -2], [3, 6]]); ctx.fill();
  ctx.fillStyle = "#c9cedd";
  poly([[-3, 4], [-26, 12], [-26, 16], [-3, 10]]); ctx.fill();
  poly([[3, 4], [26, 12], [26, 16], [3, 10]]); ctx.fill();

  // strisce rosse
  ctx.fillStyle = "#c43b3b";
  ctx.fillRect(-19, 9.2, 7, 3.4);
  ctx.fillRect(12, 9.2, 7, 3.4);

  // cannoni alle estremità
  ctx.strokeStyle = "#7e8598";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-25, 12); ctx.lineTo(-25, 0);
  ctx.moveTo(25, 12); ctx.lineTo(25, 0);
  ctx.moveTo(-23, -4); ctx.lineTo(-23, -13);
  ctx.moveTo(23, -4); ctx.lineTo(23, -13);
  ctx.stroke();

  // fusoliera
  ctx.fillStyle = "#e3e6f0";
  poly([[0, -27], [4, -8], [3.2, 15], [-3.2, 15], [-4, -8]]); ctx.fill();
  ctx.strokeStyle = "#5d6478"; ctx.lineWidth = 1; ctx.stroke();
  ctx.fillStyle = "#28303f";
  ctx.fillRect(-2.2, -6, 4.4, 7); // cockpit
  ctx.fillStyle = "#c43b3b";
  poly([[0, -27], [1.8, -18], [-1.8, -18]]); ctx.fill(); // muso
  ctx.restore();
}

function drawTIE(x, y) {
  ctx.save();
  ctx.translate(x, y);
  ctx.fillStyle = "#2c3347";
  ctx.strokeStyle = "#5a6785";
  ctx.lineWidth = 1.5;
  poly([[-12, -15], [-18, -10], [-18, 10], [-12, 15]]); ctx.fill(); ctx.stroke();
  poly([[12, -15], [18, -10], [18, 10], [12, 15]]); ctx.fill(); ctx.stroke();
  ctx.fillStyle = "#4a5570";
  ctx.fillRect(-12, -2, 24, 4);
  ctx.fillStyle = "#39415a";
  ctx.beginPath(); ctx.arc(0, 0, 8, 0, TAU); ctx.fill();
  ctx.strokeStyle = "#6b7899"; ctx.stroke();
  ctx.fillStyle = "rgba(140,170,215,0.8)";
  ctx.beginPath(); ctx.arc(0, 0, 3.4, 0, TAU); ctx.fill();
  ctx.restore();
}

function drawXWingBack(sx, sy, size, bank, flick, tick) {
  ctx.save();
  ctx.translate(sx, sy);
  ctx.rotate(bank);
  if (flick) ctx.globalAlpha = 0.45 + 0.3 * Math.sin(G.time * 30);
  const s = size;

  // 4 ali a X
  const wings = [[-1, -0.62], [1, -0.62], [-1, 0.62], [1, 0.62]];
  for (const [wx, wy] of wings) {
    ctx.fillStyle = wy < 0 ? "#c9cedd" : "#aab0c2";
    poly([
      [wx * s * 0.12, wy * s * 0.05],
      [wx * s, wy * s * 0.55],
      [wx * s, wy * s * 0.72],
      [wx * s * 0.12, wy * s * 0.22],
    ]);
    ctx.fill();
    ctx.strokeStyle = "#59607a"; ctx.lineWidth = 1; ctx.stroke();
    // striscia rossa
    ctx.fillStyle = "#c43b3b";
    ctx.fillRect(wx * s * 0.55 - s * 0.06, wy * s * 0.36 - s * 0.02, s * 0.12, s * 0.07);
    // cannone di estremità
    ctx.fillStyle = "#39415a";
    ctx.beginPath(); ctx.arc(wx * s, wy * s * 0.63, Math.max(1.4, s * 0.045), 0, TAU); ctx.fill();
  }

  // motori incandescenti
  const eg = 0.55 + 0.45 * Math.sin((tick || 0) * 21);
  for (const [wx, wy] of wings) {
    const ex = wx * s * 0.34, ey = wy * s * 0.30;
    const gr = ctx.createRadialGradient(ex, ey, 0, ex, ey, s * 0.11);
    gr.addColorStop(0, "rgba(255,150,150," + (0.85 * eg + 0.15) + ")");
    gr.addColorStop(0.5, "rgba(255,90,70,0.6)");
    gr.addColorStop(1, "rgba(255,90,70,0)");
    ctx.fillStyle = gr;
    ctx.beginPath(); ctx.arc(ex, ey, s * 0.11, 0, TAU); ctx.fill();
  }

  // fusoliera vista da dietro
  ctx.fillStyle = "#e3e6f0";
  ctx.beginPath(); ctx.arc(0, 0, s * 0.15, 0, TAU); ctx.fill();
  ctx.strokeStyle = "#59607a"; ctx.stroke();
  ctx.fillStyle = "#28303f";
  ctx.beginPath(); ctx.arc(0, -s * 0.04, s * 0.07, 0, TAU); ctx.fill();
  ctx.restore();
}

// ---------------------------------------------------------- laser & particelle (schermo)
function drawBolt(x, y, dx, dy, len, color, coreColor, width) {
  const nx = dx, ny = dy;
  ctx.lineCap = "round";
  ctx.strokeStyle = color;
  ctx.globalAlpha = 0.45;
  ctx.lineWidth = width * 2.6;
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - nx * len, y - ny * len); ctx.stroke();
  ctx.globalAlpha = 1;
  ctx.strokeStyle = coreColor;
  ctx.lineWidth = width;
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - nx * len, y - ny * len); ctx.stroke();
}

function spawnBurst(list, x, y, n, cols, speed, life) {
  for (let i = 0; i < n; i++) {
    const a = rand(0, TAU), v = rand(speed * 0.25, speed);
    list.push({
      x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v,
      life: rand(life * 0.5, life), maxLife: life,
      col: cols[Math.floor(Math.random() * cols.length)],
      size: rand(1.5, 3.5),
    });
  }
}

function updateParts(list, dt) {
  for (let i = list.length - 1; i >= 0; i--) {
    const p = list[i];
    p.x += p.vx * dt; p.y += p.vy * dt;
    p.vx *= 0.985; p.vy *= 0.985;
    p.life -= dt;
    if (p.life <= 0) list.splice(i, 1);
  }
}

function drawParts(list) {
  for (const p of list) {
    ctx.globalAlpha = clamp(p.life / p.maxLife, 0, 1);
    ctx.fillStyle = p.col;
    ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
  }
  ctx.globalAlpha = 1;
}

const EXPL_COLS = ["#ffd98a", "#ff9d4d", "#ff5c33", "#ffffff", "#ffe9c9"];

// ============================================================
// FASE 1 — BATTAGLIA SPAZIALE
// ============================================================
let space = null;

function initSpace() {
  space = {
    player: { x: W / 2, y: H * 0.8, lives: 3, shield: 3, inv: 0 },
    lasers: [], ebolts: [], enemies: [], parts: [],
    wave: 1, state: "intro", stateT: 1.6, t: 0,
    queue: [], fireCd: 0, tip: 0,
    scroll: 0, kills: 0,
  };
  G.spaceStartScore = G.score;
  buildWave(1);
  showMsg("ONDATA 1 / 3", 1.6);
  AudioFX.wave();
}

function buildWave(n) {
  const q = [];
  if (n === 1) {
    const lanes = [0.25, 0.75, 0.4, 0.6, 0.3, 0.7, 0.5, 0.55];
    lanes.forEach((lx, i) => q.push({ t: i * 1.05, type: "drift", x: lx, sp: 95, amp: 55 }));
  } else if (n === 2) {
    for (let i = 0; i < 6; i++) q.push({ t: i * 0.9, type: "drift", x: 0.2 + 0.6 * ((i * 37) % 100) / 100, sp: 115, amp: 75 });
    for (let i = 0; i < 6; i++) q.push({ t: 2 + i * 1.5, type: "diver", x: 0.15 + 0.7 * ((i * 53) % 100) / 100 });
  } else {
    for (let i = 0; i < 9; i++) q.push({ t: i * 0.75, type: "drift", x: 0.15 + 0.7 * ((i * 41) % 100) / 100, sp: 130, amp: 95 });
    for (let i = 0; i < 7; i++) q.push({ t: 1.5 + i * 1.2, type: "diver", x: 0.1 + 0.8 * ((i * 67) % 100) / 100 });
  }
  q.sort((a, b) => a.t - b.t);
  space.queue = q;
  space.t = 0;
}

function spawnEnemy(spec) {
  const e = {
    type: spec.type,
    x: spec.x * W, y: -40,
    baseX: spec.x * W,
    t: rand(0, TAU),
    hp: 1,
    fireCd: rand(1.2, 2.8) + (3 - space.wave) * 0.5,
  };
  if (spec.type === "drift") { e.sp = spec.sp; e.amp = spec.amp; }
  else { e.state = "enter"; e.hoverY = rand(H * 0.16, H * 0.3); e.hoverT = rand(0.5, 1.0); e.vx = 0; e.vy = 0; }
  space.enemies.push(e);
}

function spaceHitPlayer() {
  const p = space.player;
  if (p.inv > 0) return;
  p.shield--;
  AudioFX.hit();
  G.shake = 12;
  spawnBurst(space.parts, p.x, p.y, 10, ["#7fd4ff", "#ffffff"], 160, 0.5);
  if (p.shield < 0) {
    p.lives--;
    spawnBurst(space.parts, p.x, p.y, 30, EXPL_COLS, 260, 0.9);
    AudioFX.boom();
    if (p.lives <= 0) {
      gameOver("space", "Il tuo caccia è stato abbattuto tra le stelle.");
      return;
    }
    p.shield = 3;
    p.inv = 2.5;
    p.x = W / 2; p.y = H * 0.85;
  } else {
    p.inv = 1.4;
  }
}

function updateSpace(dt) {
  const sp = space, p = sp.player;
  sp.scroll += dt * 0.045;
  p.inv = Math.max(0, p.inv - dt);

  if (sp.state === "intro") {
    sp.stateT -= dt;
    if (sp.stateT <= 0) sp.state = "run";
  } else if (sp.state === "clear") {
    sp.stateT -= dt;
    if (sp.stateT <= 0) {
      G.screen = "approach";
      approach = { t: 0 };
      return;
    }
  }

  // movimento giocatore (tastiera)
  const mv = 380 * dt;
  if (keys["ArrowLeft"] || keys["KeyA"]) p.x -= mv;
  if (keys["ArrowRight"] || keys["KeyD"]) p.x += mv;
  if (keys["ArrowUp"] || keys["KeyW"]) p.y -= mv;
  if (keys["ArrowDown"] || keys["KeyS"]) p.y += mv;
  p.x = clamp(p.x, 22, W - 22);
  p.y = clamp(p.y, H * 0.35, H - 34);
  p.vx = (keys["ArrowLeft"] || keys["KeyA"]) ? -380 : (keys["ArrowRight"] || keys["KeyD"]) ? 380 : 0;

  // fuoco giocatore (bolt rossi come i caccia ribelli)
  sp.fireCd -= dt;
  if (fireHeld() && sp.fireCd <= 0 && sp.state === "run") {
    const tips = [[-25, -2], [25, -2], [-23, -14], [23, -14]];
    const tp = tips[sp.tip % 4]; sp.tip++;
    sp.lasers.push({ x: p.x + tp[0], y: p.y + tp[1], vy: -640 });
    sp.fireCd = 0.15;
    AudioFX.laser();
  }

  // spawn nemici
  if (sp.state === "run") {
    sp.t += dt;
    while (sp.queue.length && sp.queue[0].t <= sp.t) spawnEnemy(sp.queue.shift());
  }

  // nemici
  for (let i = sp.enemies.length - 1; i >= 0; i--) {
    const e = sp.enemies[i];
    e.t += dt;
    if (e.type === "drift") {
      e.y += e.sp * dt;
      e.x = e.baseX + Math.sin(e.t * 1.7) * e.amp;
    } else {
      if (e.state === "enter") {
        e.y += 150 * dt;
        if (e.y >= e.hoverY) e.state = "hover";
      } else if (e.state === "hover") {
        e.hoverT -= dt;
        e.x += Math.sin(e.t * 3) * 40 * dt;
        if (e.hoverT <= 0) {
          e.state = "dive";
          const d = Math.hypot(p.x - e.x, p.y - e.y) || 1;
          e.vx = ((p.x - e.x) / d) * 330;
          e.vy = ((p.y - e.y) / d) * 330;
          AudioFX.enemyLaser();
        }
      } else {
        e.x += e.vx * dt; e.y += e.vy * dt;
      }
    }

    // fuoco nemico (bolt verdi imperiali)
    e.fireCd -= dt;
    if (e.fireCd <= 0 && e.y > 0 && e.y < H * 0.7 && sp.ebolts.length < 8 + sp.wave * 4) {
      const d = Math.hypot(p.x - e.x, p.y - e.y) || 1;
      const spd = 230 + sp.wave * 25;
      const spread = rand(-0.12, 0.12);
      const ca = Math.cos(spread), sa = Math.sin(spread);
      const dx = (p.x - e.x) / d, dy = (p.y - e.y) / d;
      sp.ebolts.push({ x: e.x, y: e.y, vx: (dx * ca - dy * sa) * spd, vy: (dx * sa + dy * ca) * spd });
      e.fireCd = rand(1.3, 2.9) - sp.wave * 0.15;
      AudioFX.enemyLaser();
    }

    if (e.y > H + 60 || e.x < -80 || e.x > W + 80) { sp.enemies.splice(i, 1); continue; }

    // collisione con il giocatore
    if (p.inv <= 0 && dist2(e.x, e.y, p.x, p.y) < 30 * 30) {
      sp.enemies.splice(i, 1);
      spawnBurst(sp.parts, e.x, e.y, 22, EXPL_COLS, 240, 0.8);
      spaceHitPlayer();
      continue;
    }
  }

  // laser giocatore
  for (let i = sp.lasers.length - 1; i >= 0; i--) {
    const l = sp.lasers[i];
    l.y += l.vy * dt;
    if (l.y < -40) { sp.lasers.splice(i, 1); continue; }
    for (let j = sp.enemies.length - 1; j >= 0; j--) {
      const e = sp.enemies[j];
      if (dist2(l.x, l.y, e.x, e.y) < 22 * 22) {
        sp.lasers.splice(i, 1);
        sp.enemies.splice(j, 1);
        sp.kills++;
        G.score += e.type === "diver" ? 150 : 100;
        spawnBurst(sp.parts, e.x, e.y, 24, EXPL_COLS, 260, 0.85);
        AudioFX.boom();
        break;
      }
    }
  }

  // bolt nemici
  for (let i = sp.ebolts.length - 1; i >= 0; i--) {
    const b = sp.ebolts[i];
    b.x += b.vx * dt; b.y += b.vy * dt;
    if (b.y > H + 40 || b.x < -40 || b.x > W + 40) { sp.ebolts.splice(i, 1); continue; }
    if (p.inv <= 0 && dist2(b.x, b.y, p.x, p.y) < 17 * 17) {
      sp.ebolts.splice(i, 1);
      spaceHitPlayer();
    }
  }

  updateParts(sp.parts, dt);

  // ondata completata
  if (sp.state === "run" && sp.queue.length === 0 && sp.enemies.length === 0) {
    if (sp.wave < 3) {
      sp.wave++;
      buildWave(sp.wave);
      sp.state = "intro"; sp.stateT = 1.6;
      showMsg("ONDATA " + sp.wave + " / 3", 1.6);
      AudioFX.wave();
    } else {
      sp.state = "clear"; sp.stateT = 2.4;
      showMsg("Via libera! Rotta verso la Morte Nera…", 2.4);
      G.score += 500;
    }
  }
}

function drawSpace() {
  const sp = space, p = sp.player;
  ctx.fillStyle = "#04060c";
  ctx.fillRect(0, 0, W, H);
  drawStars(sp.scroll, 1);

  // La Morte Nera cresce all'orizzonte man mano che avanzi
  const dsR = MINWH * (0.09 + sp.wave * 0.045);
  drawDeathStar(W * 0.8, H * 0.16, dsR, 0.85, 0);

  // bolt nemici (verdi)
  for (const b of sp.ebolts) {
    const d = Math.hypot(b.vx, b.vy) || 1;
    drawBolt(b.x, b.y, b.vx / d, b.vy / d, 18, "rgba(80,255,120,0.9)", "#d8ffe0", 3);
  }
  // laser giocatore (rossi)
  for (const l of sp.lasers) drawBolt(l.x, l.y, 0, -1, 26, "rgba(255,70,60,0.9)", "#ffd9d5", 3);

  for (const e of sp.enemies) drawTIE(e.x, e.y);

  const flick = p.inv > 0 && Math.sin(G.time * 26) > 0;
  if (!flick) drawPlayerTop(p.x, p.y, p.vx || 0, false);

  drawParts(sp.parts);
  drawHUD();
  text("ONDATA " + sp.wave + "/3", W / 2, 26, 15, "#8fa2c5");
}

// ============================================================
// CUTSCENE — AVVICINAMENTO
// ============================================================
let approach = null;

function updateApproach(dt) {
  approach.t += dt;
  if (approach.t > 3.4) {
    initTrench();
    G.screen = "trench";
    AudioFX.humStart();
  }
}

function drawApproach() {
  const t = approach.t;
  ctx.fillStyle = "#04060c";
  ctx.fillRect(0, 0, W, H);

  // stelle che filano (pseudo-iperspazio)
  const cx = W / 2, cy = H / 2;
  for (const s of stars) {
    const sx = s.x * W, sy = s.y * H;
    const dx = sx - cx, dy = sy - cy;
    const stretch = 1 + t * 3 * s.z;
    ctx.strokeStyle = "rgba(200,220,255," + (0.25 + 0.5 * s.z) + ")";
    ctx.lineWidth = s.z > 0.7 ? 1.6 : 1;
    ctx.beginPath();
    ctx.moveTo(cx + dx, cy + dy);
    ctx.lineTo(cx + dx * stretch, cy + dy * stretch);
    ctx.stroke();
  }

  const k = clamp(t / 3.0, 0, 1);
  const r = lerp(MINWH * 0.22, MINWH * 1.35, k * k);
  drawDeathStar(W / 2, H * (0.35 + 0.45 * k), r, 1, 0);

  if (t > 2.6) {
    ctx.fillStyle = "rgba(255,255,255," + clamp((t - 2.6) / 0.8, 0, 1) + ")";
    ctx.fillRect(0, 0, W, H);
  }
  text("IN AVVICINAMENTO ALLA SUPERFICIE…", W / 2, H * 0.12, Math.max(15, MINWH * 0.025), "#ffe81f", "center", true);
  drawHUD();
}

// ============================================================
// FASE 2 — LA TRINCEA
// ============================================================
let trench = null;
const TR = { CAMBACK: 1.6, TOPH: 1.35, SPAWN: 50, HORIZON: 0.40, F: 800 };

const trenchGreebles = (() => {
  const rng = mulberry32(424242);
  const out = [];
  for (let i = 0; i < 46; i++) {
    out.push({
      type: "wall",
      side: rng() < 0.5 ? -1 : 1,
      y: 0.12 + rng() * 1.0,
      h: 0.06 + rng() * 0.22,
      zOff: rng() * 56,
      len: 0.8 + rng() * 2.6,
      a: 0.1 + rng() * 0.22,
    });
  }
  // strisce sul pavimento: rafforzano la sensazione di velocità e il piano del suolo
  for (let i = 0; i < 14; i++) {
    out.push({
      type: "floor",
      x: -0.85 + rng() * 1.64,
      w: 0.05 + rng() * 0.06,
      zOff: rng() * 56,
      len: 1 + rng() * 2.2,
      a: 0.08 + rng() * 0.14,
    });
  }
  return out;
})();

function initTrench() {
  trench = {
    ship: { x: 0, y: 0.55, vx: 0, vy: 0, lives: 3, shield: 3, inv: 0 },
    speed: 26,
    dist: 0,
    portAt: 1150,
    firstPortAt: 1150,
    nextSpawn: 26,
    rng: mulberry32(99173),
    obstacles: [], turrets: [], bolts: [], lasers: [], torps: [], parts3: [], parts: [],
    skyBolts: [],
    port: null,
    portWarned: false,
    torpedoes: 8,
    fireCd: 0, tip: 0,
    locked: false,
    passes: 0,
    warnObs: null,
    slowT: 0,
    hintT: 3.6,
  };
  G.trenchStartScore = G.score;
  showMsg("Vola nella trincea. Trova il condotto di scarico!", 3);
}

function proj(px, py, pz) {
  const denom = Math.max(0.18, pz + TR.CAMBACK);
  const f = TR.F;
  return {
    x: W / 2 + (px - trench.camX) * f / denom,
    y: H * TR.HORIZON - (py - trench.camY) * f / denom,
    s: f / denom,
  };
}

function trenchHitPlayer() {
  const sh = trench.ship;
  if (sh.inv > 0) return;
  sh.shield--;
  AudioFX.hit();
  G.shake = 14;
  trench.slowT = 0.9; // breve rallentamento per riprendere il controllo
  if (sh.shield < 0) {
    sh.lives--;
    AudioFX.boom();
    spawnBurst(trench.parts, W / 2, H * 0.62, 30, EXPL_COLS, 280, 0.9);
    if (sh.lives <= 0) {
      AudioFX.humStop();
      gameOver("trench", "R2 non risponde… il caccia è perduto nella trincea.");
      return;
    }
    sh.shield = 3;
    sh.inv = 2.6;
    sh.x = 0; sh.y = 0.55;
  } else {
    sh.inv = 1.5;
  }
}

function trenchSpawn() {
  const t = trench, rng = t.rng;
  const prog = clamp(t.dist / t.firstPortAt, 0, 1);
  const z = TR.SPAWN;
  const roll = rng();

  if (roll < 0.34) {
    // struttura al suolo: si passa sopra o di lato (luci ambra sul bordo alto)
    const v = rng();
    let o;
    if (v < 0.3) o = { x0: -1.05, x1: rand2(rng, -0.1, 0.3), y0: 0, y1: rand2(rng, 0.5, 0.78) };
    else if (v < 0.6) o = { x0: rand2(rng, -0.3, 0.1), x1: 1.05, y0: 0, y1: rand2(rng, 0.5, 0.78) };
    else if (v < 0.85) {
      const cx = rand2(rng, -0.35, 0.35);
      o = { x0: cx - 0.42, x1: cx + 0.42, y0: 0, y1: rand2(rng, 0.5, 0.72) };
    } else o = { x0: -1.05, x1: 1.05, y0: 0, y1: rand2(rng, 0.34, 0.46) };
    o.kind = "building"; o.z = z; o.hitDone = false;
    t.obstacles.push(o);
  } else if (roll < 0.56) {
    // ponte sospeso tra le pareti: si passa sotto (luci azzurre sul bordo basso)
    const b = rand2(rng, lerp(0.62, 0.5, prog), 0.72);
    t.obstacles.push({ kind: "bridge", x0: -1.05, x1: 1.05, y0: b, y1: b + 0.3, z, hitDone: false });
  } else if (roll < 0.72) {
    // paratia sporgente dalla parete: scarta dall'altra parte (luci rosse sul bordo libero)
    const fromLeft = rng() < 0.5;
    const wdt = rand2(rng, lerp(0.75, 0.95, prog), 1.15);
    const o = fromLeft
      ? { x0: -1.05, x1: -1.05 + wdt, innerEdge: -1.05 + wdt }
      : { x0: 1.05 - wdt, x1: 1.05, innerEdge: 1.05 - wdt };
    o.kind = "fin"; o.y0 = 0; o.y1 = TR.TOPH; o.z = z; o.hitDone = false;
    t.obstacles.push(o);
  } else if (roll < 0.82) {
    // colonna centrale (luci rosse su entrambi i bordi)
    const cx = rand2(rng, -0.4, 0.4);
    t.obstacles.push({ kind: "pillar", x0: cx - 0.2, x1: cx + 0.2, y0: 0, y1: TR.TOPH, z, hitDone: false });
  } else {
    // portale: varco illuminato in verde tra due paratie
    const gx = rand2(rng, -0.3, 0.3);
    const gh = lerp(0.34, 0.27, prog);
    t.obstacles.push({ kind: "gate", x0: -1.05, x1: gx - gh, innerEdge: gx - gh, y0: 0, y1: TR.TOPH, z, hitDone: false });
    t.obstacles.push({ kind: "gate", x0: gx + gh, x1: 1.05, innerEdge: gx + gh, y0: 0, y1: TR.TOPH, z, hitDone: false });
  }

  // ogni tanto una torretta accompagna l'ostacolo
  if (rng() < 0.35 + prog * 0.25) {
    const side = rng() < 0.6 ? (rng() < 0.5 ? "left" : "right") : "floor";
    t.turrets.push({
      side,
      x: side === "left" ? -0.9 : side === "right" ? 0.9 : rand2(rng, -0.55, 0.55),
      y: side === "floor" ? 0.09 : rand2(rng, 0.3, 0.95),
      z: z + rand2(rng, 3, 6),
      hp: 2,
      fireCd: rand2(rng, 0.7, 1.6),
      hitDone: false,
    });
  }

  t.nextSpawn = t.dist + lerp(rand2(rng, 15, 20), rand2(rng, 10.5, 14), prog);
}

const rand2 = (rng, a, b) => a + rng() * (b - a);

function fireTorpedo() {
  const t = trench;
  if (t.torpedoes <= 0) { AudioFX.hit(); showMsg("SILURI ESAURITI!", 1.2); return; }
  t.torpedoes--;
  AudioFX.torpedo();
  t.torps.push({ x: t.ship.x, y: t.ship.y - 0.05, z: 0.3, vx: 0, vy: 0 });
}

function updateTrench(dt) {
  const t = trench, sh = t.ship;
  sh.inv = Math.max(0, sh.inv - dt);
  t.slowT = Math.max(0, t.slowT - dt);
  const spd = t.slowT > 0 ? t.speed * 0.55 : t.speed;
  if (t.hintT > 0) {
    t.hintT -= dt;
    if (t.hintT <= 0) showMsg("Le luci segnano il bordo libero: ambra sopra · azzurro sotto · rosse/verdi di lato", 4);
  }
  t.camX = sh.x * 0.5;
  t.camY = sh.y * 0.5 + 0.55;
  TR.F = H * 1.05;

  // guida
  const acc = 3.4;
  let ax = 0, ay = 0;
  if (keys["ArrowLeft"] || keys["KeyA"]) ax -= acc;
  if (keys["ArrowRight"] || keys["KeyD"]) ax += acc;
  if (keys["ArrowUp"] || keys["KeyW"]) ay += acc;
  if (keys["ArrowDown"] || keys["KeyS"]) ay -= acc;
  sh.vx = clamp(sh.vx + ax * dt, -1.05, 1.05);
  sh.vy = clamp(sh.vy + ay * dt, -0.9, 0.9);
  if (!ax) sh.vx *= Math.pow(0.0009, dt);
  if (!ay) sh.vy *= Math.pow(0.0009, dt);
  sh.x = clamp(sh.x + sh.vx * dt, -0.8, 0.8);
  sh.y = clamp(sh.y + sh.vy * dt, 0.08, 1.12);

  // avanzamento
  t.dist += spd * dt;

  // spawn ostacoli finché non siamo in zona condotto
  if (!t.port && t.dist < t.portAt - 85 && t.dist >= t.nextSpawn) trenchSpawn();

  // avviso condotto
  if (!t.portWarned && t.portAt - t.dist < 70) {
    t.portWarned = true;
    showMsg("CONDOTTO DI SCARICO IN AVVICINAMENTO — SILURI PRONTI (X)", 3);
    AudioFX.lock();
  }

  // comparsa condotto
  if (!t.port && t.dist >= t.portAt) {
    t.port = { x: 0, y: 0.1, z: TR.SPAWN + 2 };
  }

  // laser (X-wing: rossi)
  t.fireCd -= dt;
  if (fireHeld() && t.fireCd <= 0) {
    const tips = [[-0.11, 0.075], [0.11, 0.075], [-0.11, -0.055], [0.11, -0.055]];
    const tp = tips[t.tip % 4]; t.tip++;
    t.lasers.push({ x: sh.x + tp[0], y: sh.y + tp[1], z: 0.4, vz: 58 });
    t.fireCd = 0.14;
    AudioFX.laser();
  }

  // siluro protonico
  if (popKey("KeyX") || popKey("ControlLeft") || popKey("ControlRight")) fireTorpedo();

  // ostacoli
  for (let i = t.obstacles.length - 1; i >= 0; i--) {
    const o = t.obstacles[i];
    o.z -= spd * dt;
    if (o.z < -1) { t.obstacles.splice(i, 1); continue; }
    if (!o.hitDone && o.z < 0.9 && o.z > -0.6 &&
        sh.x + 0.115 > o.x0 && sh.x - 0.115 < o.x1 &&
        sh.y + 0.08 > o.y0 && sh.y - 0.08 < o.y1) {
      o.hitDone = true;
      trenchHitPlayer();
      if (G.screen !== "trench") return;
    }
  }

  // rotta di collisione: l'ostacolo più vicino che colpiresti mantenendo la rotta
  t.warnObs = null;
  let warnZ = Infinity;
  for (const o of t.obstacles) {
    if (o.z > 1.2 && o.z < 30 && o.z < warnZ &&
        sh.x + 0.115 > o.x0 && sh.x - 0.115 < o.x1 &&
        sh.y + 0.08 > o.y0 && sh.y - 0.08 < o.y1) {
      warnZ = o.z; t.warnObs = o;
    }
  }
  if (t.warnObs && !t.warnObs.warned && t.warnObs.z < 22) {
    t.warnObs.warned = true;
    AudioFX.warn();
  }

  // torrette
  for (let i = t.turrets.length - 1; i >= 0; i--) {
    const tur = t.turrets[i];
    tur.z -= spd * dt;
    if (tur.z < -1) { t.turrets.splice(i, 1); continue; }
    tur.fireCd -= dt;
    const prog = clamp(t.dist / t.firstPortAt, 0, 1);
    if (tur.fireCd <= 0 && tur.z > 7 && tur.z < 38 && t.bolts.length < 10) {
      const closing = spd + 11;
      const tt = tur.z / closing;
      const txp = clamp(sh.x + sh.vx * tt * 0.7 + rand(-0.14, 0.14), -0.95, 0.95);
      const typ = clamp(sh.y + sh.vy * tt * 0.7 + rand(-0.12, 0.12), 0.05, 1.2);
      t.bolts.push({
        x: tur.x, y: tur.y, z: tur.z,
        vx: (txp - tur.x) / tt, vy: (typ - tur.y) / tt, vz: -11,
      });
      tur.fireCd = lerp(rand(1.9, 2.6), rand(1.2, 1.9), prog);
      AudioFX.enemyLaser();
    }
    if (!tur.hitDone && tur.z < 0.7 && tur.z > -0.6 &&
        Math.abs(sh.x - tur.x) < 0.16 && Math.abs(sh.y - tur.y) < 0.14) {
      tur.hitDone = true;
      trenchHitPlayer();
      if (G.screen !== "trench") return;
    }
  }

  // bolt delle torrette
  for (let i = t.bolts.length - 1; i >= 0; i--) {
    const b = t.bolts[i];
    b.x += b.vx * dt; b.y += b.vy * dt;
    b.z += (b.vz - spd) * dt;
    if (b.z < -1.2) { t.bolts.splice(i, 1); continue; }
    if (sh.inv <= 0 && Math.abs(b.z) < 0.55 &&
        Math.abs(b.x - sh.x) < 0.12 && Math.abs(b.y - sh.y) < 0.10) {
      t.bolts.splice(i, 1);
      trenchHitPlayer();
      if (G.screen !== "trench") return;
    }
  }

  // laser del giocatore
  for (let i = t.lasers.length - 1; i >= 0; i--) {
    const l = t.lasers[i];
    l.z += (l.vz + spd) * dt * 0.9;
    let dead = l.z > TR.SPAWN + 4;
    if (!dead) {
      for (let j = t.turrets.length - 1; j >= 0; j--) {
        const tur = t.turrets[j];
        if (Math.abs(l.z - tur.z) < 1.6 && Math.abs(l.x - tur.x) < 0.22 && Math.abs(l.y - tur.y) < 0.2) {
          tur.hp--;
          dead = true;
          spawn3Burst(t, tur.x, tur.y, tur.z, 6, ["#ffd98a", "#ffffff"]);
          if (tur.hp <= 0) {
            t.turrets.splice(j, 1);
            G.score += 150;
            spawn3Burst(t, tur.x, tur.y, tur.z, 18, EXPL_COLS);
            AudioFX.boom();
          }
          break;
        }
      }
    }
    if (!dead) {
      for (const o of t.obstacles) {
        if (Math.abs(l.z - o.z) < 1.2 && l.x > o.x0 && l.x < o.x1 && l.y > o.y0 && l.y < o.y1) {
          dead = true;
          spawn3Burst(t, l.x, l.y, o.z, 4, ["#9fb4d8"]);
          break;
        }
      }
    }
    if (dead) t.lasers.splice(i, 1);
  }

  // siluri protonici
  for (let i = t.torps.length - 1; i >= 0; i--) {
    const tp = t.torps[i];
    const closing = 30 + spd;
    tp.z += closing * dt;
    if (t.port) {
      const k = 3.2 * dt;
      tp.vx += (t.port.x - tp.x) * k;
      tp.vy += (t.port.y - tp.y) * k;
    }
    tp.x += tp.vx * dt; tp.y += tp.vy * dt;

    // impatto con torrette (esplosione ad area)
    for (let j = t.turrets.length - 1; j >= 0; j--) {
      const tur = t.turrets[j];
      if (Math.abs(tp.z - tur.z) < 1.6 && Math.abs(tp.x - tur.x) < 0.4 && Math.abs(tp.y - tur.y) < 0.4) {
        t.turrets.splice(j, 1);
        G.score += 150;
        spawn3Burst(t, tur.x, tur.y, tur.z, 22, EXPL_COLS);
        AudioFX.boom();
        t.torps.splice(i, 1);
        tp.deadFlag = true;
        break;
      }
    }
    if (tp.deadFlag) continue;

    // impatto con barriere
    let boom = false;
    for (const o of t.obstacles) {
      if (Math.abs(tp.z - o.z) < 1.2 && tp.x > o.x0 && tp.x < o.x1 && tp.y > o.y0 && tp.y < o.y1) {
        boom = true;
        spawn3Burst(t, tp.x, tp.y, o.z, 16, EXPL_COLS);
        AudioFX.boom();
        break;
      }
    }
    if (boom) { t.torps.splice(i, 1); continue; }

    // il colpo decisivo
    if (t.port && tp.z >= t.port.z) {
      const dx = tp.x - t.port.x, dy = tp.y - t.port.y;
      if (dx * dx + dy * dy < 0.34 * 0.34) {
        // COLPITO!
        t.torps.splice(i, 1);
        t.warnObs = null;
        G.score += 5000 + t.torpedoes * 500;
        saveHi();
        AudioFX.bigBoom();
        AudioFX.humStop();
        vseq = { t: 0, boomed: false, rings: [], parts: [], flashes: [] };
        G.screen = "vseq";
        return;
      }
    }
    if (tp.z > TR.SPAWN + 8) t.torps.splice(i, 1);
  }

  // condotto mancato?
  if (t.port) {
    t.port.z -= spd * dt;
    if (t.port.z < 1.2) {
      t.port = null;
      t.passes++;
      if (t.torpedoes <= 0 && t.torps.length === 0) {
        AudioFX.humStop();
        gameOver("trench", "Siluri esauriti: il condotto è rimasto intatto.");
        return;
      }
      t.portAt = t.dist + 300;
      t.portWarned = false;
      t.nextSpawn = t.dist + 24;
      showMsg("Mancato! Nuovo passaggio sulla trincea…", 2.6);
    }
  }

  // lock del computer di puntamento
  const wasLocked = t.locked;
  t.locked = !!(t.port && t.port.z < 18 && Math.abs(sh.x - t.port.x) < 0.42);
  if (t.locked && !wasLocked) AudioFX.lock();

  // particelle 3D
  for (let i = t.parts3.length - 1; i >= 0; i--) {
    const p = t.parts3[i];
    p.x += p.vx * dt; p.y += p.vy * dt; p.z -= spd * dt;
    p.life -= dt;
    if (p.life <= 0 || p.z < -1) t.parts3.splice(i, 1);
  }
  updateParts(t.parts, dt);

  // turbolaser ambientali nel cielo
  if (Math.random() < dt * 2.2) {
    t.skyBolts.push({ x: rand(0.1, 0.9), life: 0.5, maxLife: 0.5, dir: Math.random() < 0.5 ? -1 : 1 });
  }
  for (let i = t.skyBolts.length - 1; i >= 0; i--) {
    t.skyBolts[i].life -= dt;
    if (t.skyBolts[i].life <= 0) t.skyBolts.splice(i, 1);
  }
}

function spawn3Burst(t, x, y, z, n, cols) {
  for (let i = 0; i < n; i++) {
    t.parts3.push({
      x, y, z,
      vx: rand(-0.8, 0.8), vy: rand(-0.8, 0.8),
      life: rand(0.3, 0.7), maxLife: 0.7,
      col: cols[Math.floor(Math.random() * cols.length)],
    });
  }
}

function drawTrench(noHud) {
  const t = trench, sh = t.ship;
  TR.F = H * 1.05;
  t.camX = sh.x * 0.5;
  t.camY = sh.y * 0.5 + 0.55;

  ctx.fillStyle = "#04060c";
  ctx.fillRect(0, 0, W, H);
  drawStars(0.02 * t.dist * 0.001, 0.3);

  // turbolaser lontani nel cielo
  for (const sb of t.skyBolts) {
    const a = sb.life / sb.maxLife;
    ctx.strokeStyle = "rgba(90,255,130," + (a * 0.7).toFixed(2) + ")";
    ctx.lineWidth = 2;
    const bx = sb.x * W;
    ctx.beginPath();
    ctx.moveTo(bx, H * TR.HORIZON * (0.9 - 0.5 * a));
    ctx.lineTo(bx + sb.dir * 30, H * TR.HORIZON * (0.9 - 0.5 * a) - 60);
    ctx.stroke();
  }

  const zn = -1.1, zf = TR.SPAWN;
  const c = (px, py, pz) => proj(px, py, pz);

  // pavimento
  let p1 = c(-1, 0, zn), p2 = c(1, 0, zn), p3 = c(1, 0, zf), p4 = c(-1, 0, zf);
  poly([[p1.x, p1.y], [p2.x, p2.y], [p3.x, p3.y], [p4.x, p4.y]]);
  ctx.fillStyle = "#12151d"; ctx.fill();
  // muro sinistro
  p1 = c(-1, 0, zn); p2 = c(-1, 0, zf); p3 = c(-1, TR.TOPH, zf); p4 = c(-1, TR.TOPH, zn);
  poly([[p1.x, p1.y], [p2.x, p2.y], [p3.x, p3.y], [p4.x, p4.y]]);
  ctx.fillStyle = "#1e2534"; ctx.fill();
  // muro destro
  p1 = c(1, 0, zn); p2 = c(1, 0, zf); p3 = c(1, TR.TOPH, zf); p4 = c(1, TR.TOPH, zn);
  poly([[p1.x, p1.y], [p2.x, p2.y], [p3.x, p3.y], [p4.x, p4.y]]);
  ctx.fillStyle = "#182031"; ctx.fill();

  // spigoli della trincea: definiscono pavimento e cima delle pareti
  for (const [ex, ey, col] of [
    [-1, 0, "rgba(120,150,200,0.4)"], [1, 0, "rgba(120,150,200,0.4)"],
    [-1, TR.TOPH, "rgba(150,180,255,0.3)"], [1, TR.TOPH, "rgba(150,180,255,0.3)"],
  ]) {
    const e1 = c(ex, ey, zn), e2 = c(ex, ey, zf);
    ctx.strokeStyle = col;
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(e1.x, e1.y); ctx.lineTo(e2.x, e2.y); ctx.stroke();
  }

  // greeble su pareti e pavimento (si muovono con la distanza percorsa)
  for (const gr of trenchGreebles) {
    let gz = (gr.zOff - t.dist) % 56;
    if (gz < 0) gz += 56;
    gz -= 6;
    if (gz < 0.2 || gz > zf - 2) continue;
    ctx.fillStyle = "rgba(120,145,190," + gr.a.toFixed(2) + ")";
    if (gr.type === "floor") {
      const a1 = c(gr.x, 0.003, gz), a2 = c(gr.x + gr.w, 0.003, gz);
      const b1 = c(gr.x + gr.w, 0.003, gz + gr.len), b2 = c(gr.x, 0.003, gz + gr.len);
      poly([[a1.x, a1.y], [a2.x, a2.y], [b1.x, b1.y], [b2.x, b2.y]]);
    } else {
      const a1 = c(gr.side, gr.y, gz), a2 = c(gr.side, gr.y, gz + gr.len);
      const b1 = c(gr.side, gr.y + gr.h, gz + gr.len), b2 = c(gr.side, gr.y + gr.h, gz);
      poly([[a1.x, a1.y], [a2.x, a2.y], [b1.x, b1.y], [b2.x, b2.y]]);
    }
    ctx.fill();
  }

  // linee longitudinali
  ctx.lineWidth = 1;
  ctx.strokeStyle = "rgba(90,120,170,0.22)";
  for (const lx of [-0.6, -0.2, 0.2, 0.6]) {
    const a = c(lx, 0, zn), b = c(lx, 0, zf);
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  }
  for (const side of [-1, 1]) for (const ly of [0.45, 0.9]) {
    const a = c(side, ly, zn), b = c(side, ly, zf);
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  }

  // anelli trasversali (danno la sensazione di velocità)
  const spacing = 4;
  let zr = spacing - (t.dist % spacing);
  for (; zr < zf; zr += spacing) {
    const a = clamp(0.9 - zr / zf, 0.05, 0.45);
    ctx.strokeStyle = "rgba(90,140,210," + a.toFixed(2) + ")";
    ctx.lineWidth = zr < 6 ? 2 : 1;
    const q1 = c(-1, TR.TOPH, zr), q2 = c(-1, 0, zr), q3 = c(1, 0, zr), q4 = c(1, TR.TOPH, zr);
    ctx.beginPath();
    ctx.moveTo(q1.x, q1.y); ctx.lineTo(q2.x, q2.y); ctx.lineTo(q3.x, q3.y); ctx.lineTo(q4.x, q4.y);
    ctx.stroke();
  }

  // nebbia di distanza verso il punto di fuga
  const fog = ctx.createRadialGradient(W / 2, H * TR.HORIZON, 2, W / 2, H * TR.HORIZON, H * 0.55);
  fog.addColorStop(0, "rgba(4,6,12,0.95)");
  fog.addColorStop(0.35, "rgba(4,6,12,0.4)");
  fog.addColorStop(1, "rgba(4,6,12,0)");
  ctx.fillStyle = fog;
  ctx.fillRect(0, 0, W, H);

  // lista di disegno ordinata per profondità (prima il lontano)
  const items = [];
  if (t.port) items.push({ z: t.port.z, fn: () => drawPort(t.port) });
  for (const o of t.obstacles) items.push({ z: o.z, fn: () => drawObstacle(o) });
  for (const tur of t.turrets) items.push({ z: tur.z, fn: () => drawTurret(tur) });
  for (const b of t.bolts) items.push({ z: b.z, fn: () => drawTrenchBolt(b, "rgba(80,255,120,0.95)", "#e2ffe8") });
  for (const l of t.lasers) items.push({ z: l.z, fn: () => drawTrenchBolt(l, "rgba(255,70,60,0.95)", "#ffe2df") });
  for (const tp of t.torps) items.push({ z: tp.z, fn: () => drawTorpedo(tp) });
  for (const p of t.parts3) items.push({ z: p.z, fn: () => drawPart3(p) });
  items.sort((a, b) => b.z - a.z);
  for (const it of items) it.fn();

  // ombra del caccia sul pavimento + linea di quota tratteggiata
  const shp = proj(sh.x, 0, 0.3);
  ctx.fillStyle = "rgba(0,0,0,0.4)";
  ctx.beginPath();
  ctx.ellipse(shp.x, shp.y, MINWH * 0.06 * (1.3 - sh.y * 0.6), MINWH * 0.013, 0, 0, TAU);
  ctx.fill();

  const sp2 = proj(sh.x, sh.y, 0);
  ctx.setLineDash([5, 6]);
  ctx.strokeStyle = "rgba(140,180,255,0.3)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(sp2.x, sp2.y + MINWH * 0.02);
  ctx.lineTo(shp.x, shp.y);
  ctx.stroke();
  ctx.setLineDash([]);

  // il caccia
  const flick = sh.inv > 0;
  drawXWingBack(sp2.x, sp2.y, MINWH * 0.085, clamp(-sh.vx * 0.55, -0.6, 0.6), flick, G.time);

  // reticolo di puntamento
  if (t.port) drawTargeting();

  if (!noHud) {
    drawHUD();
    drawTrenchHUD();
  }
}

// Ogni famiglia di ostacoli ha una palette e un colore-luce che dice come superarlo:
// ambra = passa sopra · azzurro = passa sotto · rosso = scarta di lato · verde = varco sicuro.
const OB_PAL = {
  building: { front: "#453f33", top: "#6e6450", side: "#332f26", back: "#2a271f", edge: "#8a7c5e", light: "#ffb347" },
  bridge:   { front: "#33415c", top: "#54688c", side: "#273349", back: "#202b3d", edge: "#6c86b8", light: "#6fd6ff" },
  fin:      { front: "#472f36", top: "#6b4650", side: "#35232a", back: "#291b20", edge: "#8f5a6a", light: "#ff6b6b" },
  pillar:   { front: "#472f36", top: "#6b4650", side: "#35232a", back: "#291b20", edge: "#8f5a6a", light: "#ff6b6b" },
  gate:     { front: "#472f36", top: "#6b4650", side: "#35232a", back: "#291b20", edge: "#8f5a6a", light: "#59ff8a" },
};
const OB_DEPTH = 1.4;

// Scatola prospettica: mostra il "sopra" solo se la camera è più in alto e il
// "sotto" solo se è più in basso — così si legge subito se un blocco è a terra
// o sospeso, e se sei alla quota giusta per superarlo.
function drawBox3D(x0, x1, y0, y1, z0, depth, pal, warn, grooves) {
  const z1 = z0 + depth;
  const f = [proj(x0, y0, z0), proj(x1, y0, z0), proj(x1, y1, z0), proj(x0, y1, z0)];
  const b = [proj(x0, y0, z1), proj(x1, y0, z1), proj(x1, y1, z1), proj(x0, y1, z1)];
  ctx.fillStyle = pal.back;
  poly(b.map(p => [p.x, p.y])); ctx.fill();
  if (trench.camY > y1) {
    ctx.fillStyle = pal.top;
    poly([[f[3].x, f[3].y], [f[2].x, f[2].y], [b[2].x, b[2].y], [b[3].x, b[3].y]]); ctx.fill();
  }
  if (trench.camY < y0) {
    ctx.fillStyle = pal.side;
    poly([[f[0].x, f[0].y], [f[1].x, f[1].y], [b[1].x, b[1].y], [b[0].x, b[0].y]]); ctx.fill();
  }
  if (trench.camX < x0) {
    ctx.fillStyle = pal.side;
    poly([[f[0].x, f[0].y], [f[3].x, f[3].y], [b[3].x, b[3].y], [b[0].x, b[0].y]]); ctx.fill();
  }
  if (trench.camX > x1) {
    ctx.fillStyle = pal.side;
    poly([[f[1].x, f[1].y], [f[2].x, f[2].y], [b[2].x, b[2].y], [b[1].x, b[1].y]]); ctx.fill();
  }
  ctx.fillStyle = pal.front;
  poly(f.map(p => [p.x, p.y])); ctx.fill();
  // scanalature sulla faccia frontale: danno scala quando il blocco è vicino
  if (grooves && f[0].s > 120) {
    ctx.strokeStyle = "rgba(0,0,0,0.28)";
    ctx.lineWidth = 1;
    const gl = (A, B, k) => [A.x + (B.x - A.x) * k, A.y + (B.y - A.y) * k];
    for (const k of [1 / 3, 2 / 3]) {
      const a = grooves === "h" ? gl(f[0], f[3], k) : gl(f[0], f[1], k);
      const b2 = grooves === "h" ? gl(f[1], f[2], k) : gl(f[3], f[2], k);
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b2[0], b2[1]); ctx.stroke();
    }
  }
  ctx.strokeStyle = pal.edge;
  ctx.lineWidth = 1.2;
  poly(f.map(p => [p.x, p.y])); ctx.stroke();
  if (warn) {
    ctx.strokeStyle = "rgba(255,64,54," + (0.55 + 0.45 * Math.sin(G.time * 14)).toFixed(2) + ")";
    ctx.lineWidth = Math.max(2, f[0].s * 0.014);
    poly(f.map(p => [p.x, p.y])); ctx.stroke();
  }
  return f;
}

function drawGroundShadow(x0, x1, z, depth, alpha) {
  const q = [proj(x0, 0.005, z), proj(x1, 0.005, z), proj(x1, 0.005, z + depth), proj(x0, 0.005, z + depth)];
  ctx.fillStyle = "rgba(0,0,0," + alpha + ")";
  poly(q.map(p => [p.x, p.y])); ctx.fill();
}

function drawBeacon(x, y, z, color, phase) {
  const p = proj(x, y, z);
  const r = Math.max(1.8, p.s * 0.013);
  const bl = 0.6 + 0.4 * Math.sin(G.time * 6 + phase);
  const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 3.4);
  g.addColorStop(0, color);
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.globalAlpha = 0.8 * bl;
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(p.x, p.y, r * 3.4, 0, TAU); ctx.fill();
  ctx.globalAlpha = 1;
  ctx.fillStyle = color;
  ctx.beginPath(); ctx.arc(p.x, p.y, r * 0.95, 0, TAU); ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.beginPath(); ctx.arc(p.x, p.y, r * 0.4, 0, TAU); ctx.fill();
}

function drawObstacle(o) {
  const warn = o === trench.warnObs;
  const pal = OB_PAL[o.kind] || OB_PAL.building;

  if (o.kind === "bridge") {
    // ombra proiettata sul pavimento: dice subito "questo è sopra di te"
    drawGroundShadow(o.x0 + 0.06, o.x1 - 0.06, o.z + 0.15, OB_DEPTH, 0.28);
    // piloni di sostegno verso il bordo delle pareti
    for (const sx of [-0.94, 0.94]) {
      const a = proj(sx - 0.035, o.y1, o.z), b2 = proj(sx + 0.035, o.y1, o.z);
      const cT = proj(sx + 0.035, TR.TOPH, o.z), dT = proj(sx - 0.035, TR.TOPH, o.z);
      ctx.fillStyle = pal.side;
      poly([[a.x, a.y], [b2.x, b2.y], [cT.x, cT.y], [dT.x, dT.y]]); ctx.fill();
    }
    drawBox3D(o.x0, o.x1, o.y0, o.y1, o.z, OB_DEPTH, pal, warn, "h");
    // luci azzurre sul bordo basso: passa sotto le luci
    for (let i = 0; i < 5; i++) {
      const bx = lerp(o.x0 + 0.12, o.x1 - 0.12, i / 4);
      drawBeacon(bx, o.y0 - 0.015, o.z, pal.light, i * 1.3 + o.z);
    }
    return;
  }

  // tutte le altre strutture poggiano a terra: ombra di contatto
  drawGroundShadow(Math.max(o.x0, -1), Math.min(o.x1, 1), o.z, OB_DEPTH, 0.4);
  drawBox3D(o.x0, o.x1, o.y0, o.y1, o.z, OB_DEPTH, pal, warn, o.kind === "building" ? "h" : "v");

  if (o.kind === "building") {
    // luci ambra sul bordo alto: passa sopra le luci
    const xa = Math.max(o.x0, -0.98) + 0.08, xb = Math.min(o.x1, 0.98) - 0.08;
    const n = Math.max(2, Math.round((xb - xa) * 3));
    for (let i = 0; i < n; i++) {
      drawBeacon(lerp(xa, xb, n === 1 ? 0.5 : i / (n - 1)), o.y1 + 0.015, o.z, pal.light, i * 1.7 + o.z);
    }
  } else if (o.kind === "fin" || o.kind === "gate") {
    // luci sul bordo verticale libero: passa da quel lato
    for (let i = 0; i < 3; i++) {
      drawBeacon(o.innerEdge, lerp(0.15, 1.05, i / 2), o.z, pal.light, i * 1.1 + o.z);
    }
  } else if (o.kind === "pillar") {
    for (const ex of [o.x0, o.x1]) {
      for (let i = 0; i < 3; i++) {
        drawBeacon(ex, lerp(0.15, 1.05, i / 2), o.z, pal.light, i * 1.1 + ex * 4);
      }
    }
  }
}

function drawTurret(tur) {
  const p = proj(tur.x, tur.y, tur.z);
  const s = p.s * 0.09;
  ctx.save();
  ctx.translate(p.x, p.y);
  // orientata rispetto alla superficie di appoggio: canne verso l'interno della trincea
  if (tur.side === "left") ctx.rotate(Math.PI / 2);
  else if (tur.side === "right") ctx.rotate(-Math.PI / 2);
  // basamento
  ctx.fillStyle = "#333c58";
  ctx.strokeStyle = "#5a6890";
  ctx.lineWidth = 1;
  ctx.fillRect(-s, -s * 0.25, s * 2, s * 0.85);
  ctx.strokeRect(-s, -s * 0.25, s * 2, s * 0.85);
  // cupola
  ctx.fillStyle = "#465179";
  ctx.beginPath(); ctx.arc(0, -s * 0.3, s * 0.6, Math.PI, 0); ctx.fill(); ctx.stroke();
  // doppia canna che spunta dalla cupola
  ctx.strokeStyle = "#6b7ba8";
  ctx.lineWidth = Math.max(1, s * 0.16);
  ctx.beginPath();
  ctx.moveTo(-s * 0.22, -s * 0.35); ctx.lineTo(-s * 0.22, -s * 1.15);
  ctx.moveTo(s * 0.22, -s * 0.35); ctx.lineTo(s * 0.22, -s * 1.15);
  ctx.stroke();
  // luce di mira
  const warm = tur.fireCd < 0.4;
  ctx.fillStyle = warm ? "#ff5c5c" : "#7fd4ff";
  ctx.beginPath(); ctx.arc(0, -s * 0.55, Math.max(1, s * 0.16), 0, TAU); ctx.fill();
  ctx.restore();
}

function drawTrenchBolt(b, glow, core) {
  const p1 = proj(b.x, b.y, b.z);
  const p2 = proj(b.x - (b.vx || 0) * 0.02, b.y - (b.vy || 0) * 0.02, b.z + 1.1);
  ctx.lineCap = "round";
  ctx.strokeStyle = glow;
  ctx.globalAlpha = 0.45;
  ctx.lineWidth = Math.max(2, p1.s * 0.02);
  ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
  ctx.globalAlpha = 1;
  ctx.strokeStyle = core;
  ctx.lineWidth = Math.max(1, p1.s * 0.008);
  ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
}

function drawTorpedo(tp) {
  const p = proj(tp.x, tp.y, tp.z);
  const r = Math.max(2.5, p.s * 0.02);
  const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 3);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.3, "rgba(255,120,235,0.9)");
  g.addColorStop(1, "rgba(255,60,220,0)");
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(p.x, p.y, r * 3, 0, TAU); ctx.fill();
}

function drawPart3(p) {
  const pr = proj(p.x, p.y, p.z);
  ctx.globalAlpha = clamp(p.life / p.maxLife, 0, 1);
  ctx.fillStyle = p.col;
  const s = Math.max(1.5, pr.s * 0.012);
  ctx.fillRect(pr.x - s / 2, pr.y - s / 2, s, s);
  ctx.globalAlpha = 1;
}

function drawPort(port) {
  const p = proj(port.x, 0.02, port.z);
  const rx = p.s * 0.3, ry = rx * 0.32;
  const pulse = 0.6 + 0.4 * Math.sin(G.time * 7);

  // bagliore
  const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, rx * 2);
  g.addColorStop(0, "rgba(255,150,60," + (0.55 * pulse).toFixed(2) + ")");
  g.addColorStop(1, "rgba(255,120,40,0)");
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(p.x, p.y, rx * 2, 0, TAU); ctx.fill();

  // cornice ottagonale del condotto
  ctx.strokeStyle = "rgba(255,190,90," + (0.5 + 0.5 * pulse).toFixed(2) + ")";
  ctx.lineWidth = Math.max(1.5, p.s * 0.012);
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * TAU + Math.PI / 8;
    const px = p.x + Math.cos(a) * rx, py = p.y + Math.sin(a) * ry;
    i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
  }
  ctx.closePath(); ctx.stroke();

  // bocca scura
  ctx.fillStyle = "#0a0c12";
  ctx.beginPath(); ctx.ellipse(p.x, p.y, rx * 0.55, ry * 0.55, 0, 0, TAU); ctx.fill();
  ctx.strokeStyle = "rgba(255,120,50,0.9)";
  ctx.beginPath(); ctx.ellipse(p.x, p.y, rx * 0.55, ry * 0.55, 0, 0, TAU); ctx.stroke();
}

function drawTargeting() {
  const t = trench;
  const p = proj(t.port.x, t.port.y, t.port.z);
  const col = t.locked ? "#59ff8a" : "#ffe81f";
  const s = clamp(p.s * 0.16, 26, 140);
  ctx.strokeStyle = col;
  ctx.lineWidth = 2;
  const gapK = t.locked ? 0.55 : 0.75 + 0.1 * Math.sin(G.time * 5);
  for (const [mx, my] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
    ctx.beginPath();
    ctx.moveTo(p.x + mx * s, p.y + my * s * gapK);
    ctx.lineTo(p.x + mx * s, p.y + my * s);
    ctx.lineTo(p.x + mx * s * gapK, p.y + my * s);
    ctx.stroke();
  }
  text(t.locked ? "AGGANCIATO — FUOCO! (X)" : "ALLINEATI AL CONDOTTO", p.x, p.y - s - 16, 13, col, "center", true);
  const dist = Math.max(0, t.port.z).toFixed(0);
  text(dist, p.x, p.y + s + 14, 12, col);
}

function drawTrenchHUD() {
  const t = trench;
  // siluri
  ctx.textAlign = "left";
  text("SILURI", 18, H - 52, 12, "#8fa2c5", "left");
  for (let i = 0; i < 8; i++) {
    const on = i < t.torpedoes;
    ctx.fillStyle = on ? "#ff6fe0" : "rgba(120,130,160,0.25)";
    poly([[24 + i * 18, H - 24], [18 + i * 18, H - 36], [30 + i * 18, H - 36]]);
    ctx.fill();
  }
  // distanza dal condotto
  const rem = Math.max(0, t.portAt - t.dist);
  const km = (rem / t.firstPortAt * 6.2);
  text(t.port ? "CONDOTTO IN VISTA!" : "DISTANZA CONDOTTO: " + km.toFixed(1) + " km",
       W - 18, H - 30, 14, t.port ? "#ffb347" : "#8fa2c5", "right", t.port);
}

// ============================================================
// SEQUENZA FINALE — LA MORTE NERA ESPLODE
// ============================================================
let vseq = null;

function updateVseq(dt) {
  const v = vseq;
  v.t += dt;
  const t2 = v.t - 1.9;

  if (t2 > 1.2 && !v.boomed) {
    v.boomed = true;
    G.shake = 26;
    spawnBurst(v.parts, W / 2, H / 2, 260, EXPL_COLS, MINWH * 0.55, 2.6);
    v.rings.push({ r: 4, w: 10, kind: "disc" });
    v.rings.push({ r: 4, w: 6, kind: "ring" });
  }
  for (const r of v.rings) r.r += dt * MINWH * (r.kind === "disc" ? 0.75 : 0.55);
  updateParts(v.parts, dt);

  if (v.t > 7.5) {
    G.screen = "victory";
    saveHi();
    pressedCodes.clear();
    touchTapped = false;
  }
}

function drawVseq() {
  const v = vseq;

  if (v.t < 1.9) {
    // fuga dalla trincea con bagliore crescente alle spalle
    if (trench) {
      trench.ship.y = clamp(trench.ship.y + 0.35 * (1 / 60), 0, 1.3);
      drawTrench(true);
    }
    const k = clamp(v.t / 1.9, 0, 1);
    const g = ctx.createRadialGradient(W / 2, H * 0.42, 0, W / 2, H * 0.42, MINWH * (0.2 + k * 1.2));
    g.addColorStop(0, "rgba(255,240,200," + (0.85 * k).toFixed(2) + ")");
    g.addColorStop(1, "rgba(255,180,90,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    text("CENTRO PERFETTO! VIA DALLA TRINCEA!", W / 2, H * 0.2, Math.max(16, MINWH * 0.03), "#ffe81f", "center", true);
    if (v.t > 1.4) {
      ctx.fillStyle = "rgba(0,0,0," + clamp((v.t - 1.4) / 0.5, 0, 1) + ")";
      ctx.fillRect(0, 0, W, H);
    }
    return;
  }

  // vista esterna
  const t2 = v.t - 1.9;
  ctx.fillStyle = "#04060c";
  ctx.fillRect(0, 0, W, H);
  drawStars(0, 0.15);

  const R = MINWH * 0.3;
  if (!v.boomed) {
    // piccoli lampi premonitori sulla superficie
    const dmg = clamp(t2 / 1.2, 0, 1);
    drawDeathStar(W / 2, H / 2, R, 1, dmg * 0.9);
    if (Math.random() < 0.35) {
      ctx.fillStyle = "rgba(255,240,200,0.9)";
      const a = rand(0, TAU), rr = rand(0, R * 0.8);
      ctx.beginPath();
      ctx.arc(W / 2 + Math.cos(a) * rr, H / 2 + Math.sin(a) * rr, rand(1.5, 4), 0, TAU);
      ctx.fill();
    }
  } else {
    const sinceBoom = t2 - 1.2;
    const dsA = clamp(1 - sinceBoom * 1.6, 0, 1);
    if (dsA > 0) drawDeathStar(W / 2, H / 2, R * (1 + sinceBoom * 0.7), dsA, 1);

    // anelli d'urto
    for (const r of v.rings) {
      const a = clamp(1.6 - r.r / (MINWH * 0.9), 0, 1);
      if (a <= 0) continue;
      ctx.lineWidth = r.w * a + 1;
      if (r.kind === "disc") {
        ctx.strokeStyle = "rgba(180,220,255," + a.toFixed(2) + ")";
        ctx.beginPath(); ctx.ellipse(W / 2, H / 2, r.r * 2.1, r.r * 0.45, 0, 0, TAU); ctx.stroke();
      } else {
        ctx.strokeStyle = "rgba(255,235,190," + a.toFixed(2) + ")";
        ctx.beginPath(); ctx.arc(W / 2, H / 2, r.r, 0, TAU); ctx.stroke();
      }
    }
    drawParts(v.parts);

    // lampo iniziale
    const fl = clamp(1 - sinceBoom / 0.7, 0, 1);
    if (fl > 0) {
      ctx.fillStyle = "rgba(255,255,255," + fl.toFixed(2) + ")";
      ctx.fillRect(0, 0, W, H);
    }
    if (sinceBoom > 1.6) {
      text("LA MORTE NERA È STATA DISTRUTTA!", W / 2, H * 0.16,
           Math.max(18, MINWH * 0.042), "#ffe81f", "center", true);
    }
  }
}

// ============================================================
// SCHERMATE
// ============================================================
function gameOver(where, reason) {
  G.diedIn = where;
  G.overReason = reason;
  saveHi();
  G.screen = "gameover";
  AudioFX.humStop();
  pressedCodes.clear();
  touchTapped = false;
}

function drawTitle() {
  ctx.fillStyle = "#04060c";
  ctx.fillRect(0, 0, W, H);
  drawStars(G.time * 0.006, 1);
  drawDeathStar(W * 0.78, H * 0.28, MINWH * 0.34, 0.5, 0);

  const ty = H * 0.3;
  text("UN FAN GAME ISPIRATO A GUERRE STELLARI", W / 2, ty - MINWH * 0.09, Math.max(11, MINWH * 0.018), "#8fa2c5");
  text("ASSALTO ALLA", W / 2, ty, Math.max(26, MINWH * 0.055), "#ffe81f", "center", true);
  text("MORTE NERA", W / 2, ty + MINWH * 0.085, Math.max(38, MINWH * 0.085), "#ffe81f", "center", true);

  const cy = H * 0.62;
  const fs = Math.max(12, MINWH * 0.019);
  text("FRECCE / WASD  muovi il caccia", W / 2, cy, fs, "#c5cde0");
  text("SPAZIO  laser      X  siluro protonico", W / 2, cy + fs * 1.7, fs, "#c5cde0");
  text("P  pausa      M  audio on/off", W / 2, cy + fs * 3.4, fs, "#c5cde0");
  if (hasTouch) text("Touch: trascina a sinistra per muoverti, pulsanti a destra", W / 2, cy + fs * 5.1, fs, "#8fa2c5");

  if (Math.sin(G.time * 4) > -0.3)
    text("PREMI INVIO PER INIZIARE", W / 2, H * 0.82, Math.max(15, MINWH * 0.026), "#ffffff", "center", true);

  if (G.hi > 0) text("RECORD  " + fmtScore(G.hi), W / 2, H * 0.06, 14, "#8fa2c5");
  text("Fan game non ufficiale · nessuna affiliazione con Lucasfilm/Disney", W / 2, H - 16, 10, "#4d5670");
}

const CRAWL_LINES = [
  ["EPISODIO IV E MEZZO", true],
  ["UN NUOVO PILOTA", true],
  ["", false],
  ["È un periodo di guerra civile.", false],
  ["L'Impero ha completato la sua", false],
  ["arma definitiva: la MORTE NERA,", false],
  ["una stazione spaziale capace di", false],
  ["annientare interi pianeti.", false],
  ["", false],
  ["Le spie ribelli hanno scoperto", false],
  ["un punto debole: un piccolo", false],
  ["condotto di scarico termico", false],
  ["collegato al reattore centrale.", false],
  ["", false],
  ["Sei l'ultima speranza della", false],
  ["Alleanza. Apri un varco tra i", false],
  ["caccia imperiali, vola nella", false],
  ["trincea e centra il condotto", false],
  ["con un siluro protonico.", false],
  ["", false],
  ["Che la Forza sia con te…", true],
];
let crawl = { t: 0 };

function updateCrawl(dt) {
  crawl.t += dt;
  const lineH = MINWH * 0.055;
  const end = H + CRAWL_LINES.length * lineH;
  if (crawl.t * MINWH * 0.085 > end * 1.02 || anyStartPressed()) {
    initSpace();
    G.screen = "space";
  }
}

function drawCrawl() {
  ctx.fillStyle = "#04060c";
  ctx.fillRect(0, 0, W, H);
  drawStars(0, 1);

  const speed = MINWH * 0.085;
  const lineH = MINWH * 0.055;
  const horizon = H * 0.12;

  for (let i = 0; i < CRAWL_LINES.length; i++) {
    const [str, big] = CRAWL_LINES[i];
    if (!str) continue;
    const y = H * 0.9 + i * lineH - crawl.t * speed;
    if (y < horizon || y > H + lineH) continue;
    const k = (y - horizon) / (H - horizon); // 0 in alto, 1 in basso
    const sc = lerp(0.35, 1.15, k);
    const alpha = clamp(k * 2.2, 0, 1);
    ctx.save();
    ctx.translate(W / 2, y);
    ctx.scale(sc, sc);
    ctx.globalAlpha = alpha;
    text(str, 0, 0, big ? Math.max(20, MINWH * 0.037) : Math.max(16, MINWH * 0.03), "#ffe81f", "center", big);
    ctx.restore();
  }
  ctx.globalAlpha = 1;
  text("INVIO per saltare", W / 2, H - 20, 11, "#4d5670");
}

function drawVictory() {
  ctx.fillStyle = "#04060c";
  ctx.fillRect(0, 0, W, H);
  drawStars(0, 0.15);
  if (vseq) drawParts(vseq.parts);

  text("VITTORIA!", W / 2, H * 0.26, Math.max(34, MINWH * 0.08), "#ffe81f", "center", true);
  text("LA MORTE NERA È STATA DISTRUTTA", W / 2, H * 0.36, Math.max(15, MINWH * 0.028), "#ffffff", "center", true);
  text("La galassia è salva. Medaglia per tutti!", W / 2, H * 0.43, Math.max(12, MINWH * 0.02), "#8fa2c5");

  text("PUNTEGGIO  " + fmtScore(G.score), W / 2, H * 0.55, Math.max(16, MINWH * 0.028), "#ffffff");
  if (G.score >= G.hi) text("NUOVO RECORD!", W / 2, H * 0.61, 15, "#59ff8a", "center", true);
  else text("RECORD  " + fmtScore(G.hi), W / 2, H * 0.61, 13, "#8fa2c5");

  if (Math.sin(G.time * 4) > -0.3)
    text("INVIO: gioca ancora", W / 2, H * 0.78, Math.max(14, MINWH * 0.024), "#ffffff");
}

function drawGameOver() {
  ctx.fillStyle = "#04060c";
  ctx.fillRect(0, 0, W, H);
  drawStars(0, 0.3);

  text("GAME OVER", W / 2, H * 0.3, Math.max(34, MINWH * 0.075), "#ff5c5c", "center", true);
  text(G.overReason, W / 2, H * 0.41, Math.max(13, MINWH * 0.022), "#c5cde0");
  text("PUNTEGGIO  " + fmtScore(G.score), W / 2, H * 0.52, Math.max(15, MINWH * 0.026), "#ffffff");
  text("RECORD  " + fmtScore(G.hi), W / 2, H * 0.58, 13, "#8fa2c5");
  if (Math.sin(G.time * 4) > -0.3)
    text("INVIO: riprova la fase      ESC: torna al titolo", W / 2, H * 0.75, Math.max(13, MINWH * 0.022), "#ffffff");
}

// ---------------------------------------------------------- HUD comune
function drawHUD() {
  const lives = G.screen === "trench" || (G.screen === "vseq") ? (trench ? trench.ship.lives : 3)
              : space ? space.player.lives : 3;
  const shield = G.screen === "trench" ? (trench ? trench.ship.shield : 3)
               : space ? space.player.shield : 3;

  text("PUNTI  " + fmtScore(G.score), 18, 24, 15, "#ffffff", "left", true);

  // scudi
  ctx.textAlign = "right";
  text("SCUDI", W - 118, 22, 12, "#8fa2c5", "right");
  for (let i = 0; i < 3; i++) {
    ctx.fillStyle = i < shield ? "#5ad0ff" : "rgba(120,130,160,0.25)";
    ctx.fillRect(W - 108 + i * 22, 14, 16, 8);
  }
  // vite
  text("VITE", W - 118, 44, 12, "#8fa2c5", "right");
  for (let i = 0; i < 3; i++) {
    ctx.fillStyle = i < lives ? "#e3e6f0" : "rgba(120,130,160,0.25)";
    poly([[W - 104 + i * 22, 50], [W - 111 + i * 22, 38], [W - 97 + i * 22, 38]]);
    ctx.fill();
  }

  if (AudioFX.muted) text("AUDIO OFF (M)", W - 18, H - 12, 10, "#4d5670", "right");

  // pulsanti touch
  if (hasTouch && (G.screen === "space" || G.screen === "trench")) {
    const fb = fireBtn();
    ctx.globalAlpha = 0.35;
    ctx.strokeStyle = "#ff8c85"; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(fb.x, fb.y, fb.r, 0, TAU); ctx.stroke();
    text("FUOCO", fb.x, fb.y, 13, "#ff8c85");
    if (G.screen === "trench") {
      const tb = torpBtn();
      ctx.strokeStyle = "#ff6fe0";
      ctx.beginPath(); ctx.arc(tb.x, tb.y, tb.r, 0, TAU); ctx.stroke();
      text("SILURO", tb.x, tb.y, 12, "#ff6fe0");
    }
    ctx.globalAlpha = 1;
  }
}

function drawMsg() {
  if (G.msgT <= 0 || !G.msg) return;
  const a = clamp(G.msgT / 0.4, 0, 1);
  ctx.globalAlpha = a;
  text(G.msg, W / 2, H * 0.3, Math.max(15, MINWH * 0.027), "#ffe81f", "center", true);
  ctx.globalAlpha = 1;
}

// ============================================================
// LOOP PRINCIPALE
// ============================================================
function update(dt) {
  G.time += dt;
  G.msgT = Math.max(0, G.msgT - dt);
  G.shake = Math.max(0, G.shake - dt * 40);

  // pausa
  if ((G.screen === "space" || G.screen === "trench") && popKey("KeyP")) G.paused = !G.paused;
  if (G.paused) {
    if (popKey("Enter") || touchTapped) { G.paused = false; touchTapped = false; }
    return;
  }

  // ESC → titolo
  if (G.screen !== "title" && popKey("Escape")) {
    AudioFX.humStop();
    G.screen = "title";
    pressedCodes.clear();
    touchTapped = false;
    return;
  }

  switch (G.screen) {
    case "title":
      if (anyStartPressed()) { crawl = { t: 0 }; G.screen = "crawl"; G.score = 0; }
      break;
    case "crawl":  updateCrawl(dt); break;
    case "space":  updateSpace(dt); break;
    case "approach": updateApproach(dt); break;
    case "trench": updateTrench(dt); break;
    case "vseq":   updateVseq(dt); break;
    case "victory":
      if (vseq) updateParts(vseq.parts, dt);
      if (anyStartPressed()) G.screen = "title";
      break;
    case "gameover":
      if (anyStartPressed()) {
        if (G.diedIn === "space") { G.score = G.spaceStartScore; initSpace(); G.screen = "space"; }
        else { G.score = G.trenchStartScore; initTrench(); G.screen = "trench"; AudioFX.humStart(); }
      }
      break;
  }
}

function draw() {
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  if (G.shake > 0) ctx.translate(rand(-G.shake, G.shake) * 0.5, rand(-G.shake, G.shake) * 0.5);

  switch (G.screen) {
    case "title":    drawTitle(); break;
    case "crawl":    drawCrawl(); break;
    case "space":    drawSpace(); break;
    case "approach": drawApproach(); break;
    case "trench":   drawTrench(); break;
    case "vseq":     drawVseq(); break;
    case "victory":  drawVictory(); break;
    case "gameover": drawGameOver(); break;
  }

  drawMsg();

  if (G.paused) {
    ctx.fillStyle = "rgba(0,0,0,0.6)";
    ctx.fillRect(0, 0, W, H);
    text("PAUSA", W / 2, H / 2, Math.max(26, MINWH * 0.05), "#ffffff", "center", true);
    text("P o INVIO per continuare", W / 2, H / 2 + MINWH * 0.06, 14, "#8fa2c5");
  }
}

let last = 0;
function frame(ts) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.033, last ? (ts - last) / 1000 : 0.016);
  last = ts;
  update(dt);
  draw();
}
requestAnimationFrame(frame);

// ---------------------------------------------------------- hook di debug/test
window.__game = {
  G,
  trench: () => trench,
  space: () => space,
  startTrench() { initTrench(); G.screen = "trench"; },
  startSpace() { initSpace(); G.screen = "space"; },
  startApproach() { approach = { t: 0 }; G.screen = "approach"; },
  forceVictory() {
    G.score += 5000;
    vseq = { t: 0, boomed: false, rings: [], parts: [], flashes: [] };
    G.screen = "vseq";
  },
};
