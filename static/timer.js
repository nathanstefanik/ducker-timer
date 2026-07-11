const code = location.pathname.split("/").pop();

let state = null;
let offset = 0;  // server clock minus local clock, in seconds
let ducks = [];  // built once the first state arrives and names are known

const clock = document.getElementById("clock");
const pond = document.getElementById("pond");
const banner = document.getElementById("banner");
document.getElementById("code").textContent = code;
document.title = `${code} — duck race timer`;

function mulberry32(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const BODIES = ["#f5d442", "#fdfdf2", "#b07b3f", "#7fb069", "#d96c8e", "#8ab6d6", "#c9b1ff", "#f2a65a"];

// hand-drawn, public domain by construction. derpiness is seeded:
// independently sized googly eyes with independently wandering pupils.
function duckSvg(rand) {
  const body = BODIES[Math.floor(rand() * BODIES.length)];
  const eye = (cx) => {
    const r = 2.6 + 2.2 * rand();
    const dx = (rand() - 0.5) * 2.6;
    const dy = (rand() - 0.5) * 2.6;
    return `<circle cx="${cx}" cy="13" r="${r.toFixed(1)}" fill="#fff" stroke="#333" stroke-width="0.6"/>
      <circle cx="${(cx + dx).toFixed(1)}" cy="${(13 + dy).toFixed(1)}" r="1.7" fill="#222"/>`;
  };
  return `<svg viewBox="0 0 72 48" width="48" height="32">
    <polygon points="2,26 16,30 6,38" fill="${body}"/>
    <ellipse cx="28" cy="33" rx="22" ry="12" fill="${body}"/>
    <ellipse cx="25" cy="35" rx="11" ry="6" fill="rgba(0,0,0,0.12)"/>
    <circle cx="46" cy="16" r="11" fill="${body}"/>
    <polygon points="55,13 70,17 55,21" fill="#f28c28"/>
    ${eye(43)}${eye(50)}
  </svg>`;
}

function buildPond(names, lookSeed) {
  const rand = mulberry32(lookSeed);
  ducks = names.map((name) => {
    const lane = document.createElement("div");
    lane.className = "lane";
    const duck = document.createElement("span");
    duck.className = "duck";
    duck.innerHTML = duckSvg(rand);
    const label = document.createElement("span");
    label.className = "duck-name";
    label.textContent = name;  // textContent, not innerHTML: names are user input
    duck.prepend(label);
    lane.appendChild(duck);
    pond.appendChild(lane);
    return duck;
  });
}

// positions are a pure function of (frac, seed, names), so a viewer joining
// mid-race is instantly in sync. speeds are draws from the chosen
// distribution; the winning duck finishes exactly at frac=1, the rest are
// min-max scaled onto [0.55, 1]. the wobble vanishes at frac=0 and frac=1,
// and its 0.35 amplitude keeps finish*frac + wobble < 1 before the end:
// nobody crosses the line early.
//
// capital-letter edge (normal only): each A–Z shifts loc by MU_PER_CAP,
// capped at 10. MU_MAX = sqrt(2)*Φ⁻¹(0.75) ≈ 0.95387, so 10 caps vs a
// lowercase duck wins pairwise with probability 0.75. uniform/exponential
// draws stay iid; capitals do nothing there.
const MU_MAX = 0.95387;
const MU_PER_CAP = MU_MAX / 10;

function raceState(frac, seed, names, dist) {
  const n = names.length;
  const rand = mulberry32(seed);
  const raws = names.map((name) => {
    if (dist === "uniform") return rand();
    if (dist === "exponential") return -Math.log(1 - rand());
    const caps = Math.min((name.match(/[A-Z]/g) || []).length, 10);
    const z = Math.sqrt(-2 * Math.log(1 - rand())) * Math.cos(2 * Math.PI * rand());
    return z + caps * MU_PER_CAP;
  });
  const hi = Math.max(...raws);
  const lo = Math.min(...raws);
  const winner = raws.indexOf(hi);
  const positions = raws.map((r) => {
    const finish = 0.55 + 0.45 * (r - lo) / (hi - lo);
    const wobble = 0.35 * Math.sin(2 * Math.PI * ((2 + 4 * rand()) * frac + rand())) * frac * (1 - frac);
    return Math.max(0, Math.min(1, finish * frac + wobble));
  });
  return { positions, winner };
}

function fmt(totalS) {
  const h = Math.floor(totalS / 3600);
  const m = Math.floor((totalS % 3600) / 60);
  const s = Math.floor(totalS % 60);
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

function render() {
  if (state) {
    if (state.started_at === null) {
      clock.textContent = fmt(state.duration_s);
      banner.textContent = "";
      ducks.forEach((d) => d.style.setProperty("--pos", 0));
    } else {
      const elapsed = Math.min(Date.now() / 1000 + offset - state.started_at, state.duration_s);
      const frac = Math.max(0, elapsed) / state.duration_s;
      clock.textContent = fmt(Math.ceil(state.duration_s - elapsed));
      const { positions, winner } = raceState(frac, state.seed, state.names, state.dist);
      positions.forEach((p, i) => ducks[i].style.setProperty("--pos", p));
      banner.textContent = frac >= 1 ? `${state.names[winner]} wins 1st!` : "";
    }
  }
  requestAnimationFrame(render);
}

function adopt(data) {
  if (!ducks.length) buildPond(data.names, data.look_seed);
  if (data.title) {
    const title = document.getElementById("title");
    title.textContent = data.title;
    title.hidden = false;
    document.title = `${data.title} — duck race timer`;
  }
  state = data;
  offset = data.server_now - Date.now() / 1000;
}

async function sync() {
  const resp = await fetch(`/api/t/${code}`);
  if (resp.ok) adopt(await resp.json());
  else clock.textContent = "no such timer";
}

async function act(action) {
  const resp = await fetch(`/api/t/${code}/${action}`, { method: "POST" });
  if (resp.ok) adopt(await resp.json());
}

document.getElementById("start").addEventListener("click", (e) => {
  e.preventDefault();
  act("start");
});
document.getElementById("reset").addEventListener("click", (e) => {
  e.preventDefault();
  act("reset");
});

sync();
setInterval(sync, 3000);
requestAnimationFrame(render);
