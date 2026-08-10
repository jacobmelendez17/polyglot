#!/usr/bin/env node
/*
 * gen-hero-strokes.cjs — regenerate apps/web/lib/hero-strokes.ts (slice 36).
 *
 * This is an OFFLINE, manual tool — it is NOT part of the build or CI and adds
 * no runtime dependencies. It bakes single-stroke cursive path data for a
 * curated set of greetings so the hero can *draw* each "hello" like handwriting.
 *
 * Run it yourself when you want to change the word list or font:
 *   cd apps/web
 *   npm i --no-save hersheytext svg-path-properties
 *   node scripts/gen-hero-strokes.cjs > lib/hero-strokes.ts
 *
 * Font: public-domain Hershey "cursive" single-line font (via 'hersheytext').
 * Curated to Latin-script greetings the single-stroke font renders cleanly
 * (español + tagalog first). Non-Latin scripts have no single-stroke glyphs, so
 * they stay in the marquee / floating greetings, not here.
 */
const h = require("hersheytext");
const { svgPathProperties } = require("svg-path-properties");

const FONT = "cursive";
const WORDS = [
  ["hola", "español"], ["kumusta", "tagalog"], ["hello", "english"],
  ["bonjour", "français"], ["ciao", "italiano"], ["hallo", "deutsch"],
  ["merhaba", "türkçe"], ["jambo", "kiswahili"], ["aloha", "hawaiian"], ["oi", "português"],
];

function parse(word) {
  const svg = h.renderTextSVG(word, { font: FONT });
  const scaleM = svg.match(/scale\(([\d.]+)\)/);
  const S = scaleM ? parseFloat(scaleM[1]) : 1;
  const strokes = [];
  const re = /<path[^>]*\bd="([^"]+)"[^>]*\btransform="translate\(([-\d.]+),\s*([-\d.]+)\)"[^>]*\bletter="([^"]*)"/g;
  let m;
  while ((m = re.exec(svg)) !== null) {
    strokes.push({ d: m[1], tx: parseFloat(m[2]), ty: parseFloat(m[3]), letter: m[4] });
  }
  return { S, strokes };
}

function pathBox(props, tx, ty) {
  const L = props.getTotalLength();
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  const N = Math.max(8, Math.ceil(L / 2));
  for (let i = 0; i <= N; i++) {
    const p = props.getPointAtLength((L * i) / N);
    const x = p.x + tx, y = p.y + ty;
    if (x < minx) minx = x; if (x > maxx) maxx = x;
    if (y < miny) miny = y; if (y > maxy) maxy = y;
  }
  return { minx, miny, maxx, maxy, L };
}

const out = [];
for (const [word, lang] of WORDS) {
  const { S, strokes } = parse(word);
  const want = word.replace(/\s/g, "").split("");
  const got = strokes.map((s) => s.letter);
  const missing = want.filter((c) => !got.includes(c));
  if (missing.length) throw new Error(`${word}: missing glyphs [${missing.join(",")}]`);

  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  const norm = strokes.map((s) => {
    const props = new svgPathProperties(s.d);
    const b = pathBox(props, s.tx, s.ty);
    minx = Math.min(minx, b.minx); miny = Math.min(miny, b.miny);
    maxx = Math.max(maxx, b.maxx); maxy = Math.max(maxy, b.maxy);
    return { d: s.d, t: [s.tx, s.ty], len: +b.L.toFixed(2) };
  });
  const pad = 3;
  const vb = [
    +(minx - pad).toFixed(2), +(miny - pad).toFixed(2),
    +(maxx - minx + 2 * pad).toFixed(2), +(maxy - miny + 2 * pad).toFixed(2),
  ];
  out.push({
    text: word, lang,
    vb, aspect: +(vb[2] / vb[3]).toFixed(4),
    totalLen: +norm.reduce((a, s) => a + s.len, 0).toFixed(2),
    strokes: norm,
    _scale: S, // informational only; component sizes via em
  });
}

const banner = `// GENERATED FILE — do not edit by hand (slice 36).
//
// Single-stroke cursive path data for the hero greeting, so each "hello" can be
// *drawn* stroke-by-stroke (stroke-dashoffset) like real handwriting. Generated
// offline from the public-domain Hershey "cursive" single-line font via the
// 'hersheytext' toolkit — there is NO runtime font dependency; only this static
// path data ships. Regenerate with scripts/gen-hero-strokes.cjs. Curated to
// Latin-script greetings the single-stroke font renders cleanly.

export interface HeroStroke { d: string; t: [number, number]; len: number }
export interface HeroWord {
  text: string;
  lang: string;
  /** local viewBox [x, y, w, h] */
  vb: [number, number, number, number];
  /** width / height, for sizing the inline svg from the headline font-size */
  aspect: number;
  /** sum of all stroke lengths (constant-speed pen timing) */
  totalLen: number;
  strokes: HeroStroke[];
}

export const HERO_WORDS: HeroWord[] = `;

const clean = out.map(({ _scale, ...w }) => w); // drop informational field
process.stdout.write(banner + JSON.stringify(clean, null, 1) + ";\n");
