#!/usr/bin/env node
/*
 * gen-hero-strokes.cjs — regenerate apps/web/lib/hero-strokes.ts (slice 37).
 *
 * OFFLINE, manual tool — NOT part of the build or CI, adds no runtime deps.
 * Bakes single-stroke cursive path data for a curated set of greetings so the
 * hero can *draw* each "hello" like handwriting.
 *
 *   cd apps/web
 *   npm i --no-save hersheytext svg-path-properties
 *   node scripts/gen-hero-strokes.cjs > lib/hero-strokes.ts
 *
 * Font: public-domain Hershey "cursive" single-line font (via 'hersheytext').
 * The baseline is detected as the most common letter-bottom; each word's viewBox
 * bottom is set to that baseline so the inline SVG aligns to the text baseline,
 * with descenders overflowing below. EM_PER_UNIT / STROKE_UNITS are the tuned
 * size + pen weight (slice 37 Option A).
 */
const h = require("hersheytext");
const { svgPathProperties } = require("svg-path-properties");

const FONT = "cursive";
const EM_PER_UNIT = 0.043; // tuned so ascenders ≈ headline cap height
const STROKE_UNITS = 2.1; // tuned marker weight (scales with the word)
const WORDS = [
  ["hola", "español"], ["kumusta", "tagalog"], ["hello", "english"],
  ["bonjour", "français"], ["ciao", "italiano"], ["hallo", "deutsch"],
  ["merhaba", "türkçe"], ["jambo", "kiswahili"], ["aloha", "hawaiian"], ["oi", "português"],
];

function parse(word) {
  const svg = h.renderTextSVG(word, { font: FONT });
  const strokes = [];
  const re = /<path[^>]*\bd="([^"]+)"[^>]*\btransform="translate\(([-\d.]+),\s*([-\d.]+)\)"[^>]*\bletter="([^"]*)"/g;
  let m;
  while ((m = re.exec(svg)) !== null) strokes.push({ d: m[1], tx: +m[2], ty: +m[3], letter: m[4] });
  return strokes;
}
function box(props, tx, ty) {
  const L = props.getTotalLength();
  let a = Infinity, b = Infinity, c = -Infinity, d = -Infinity;
  const N = Math.max(10, Math.ceil(L / 1.5));
  for (let i = 0; i <= N; i++) {
    const p = props.getPointAtLength((L * i) / N);
    const x = p.x + tx, y = p.y + ty;
    if (x < a) a = x; if (x > c) c = x; if (y < b) b = y; if (y > d) d = y;
  }
  return { minx: a, miny: b, maxx: c, maxy: d, L };
}

const bottoms = [];
const perWord = [];
for (const [word, lang] of WORDS) {
  const strokes = parse(word).map((s) => {
    const props = new svgPathProperties(s.d);
    const bx = box(props, s.tx, s.ty);
    bottoms.push(Math.round(bx.maxy));
    return { d: s.d, t: [s.tx, s.ty], len: +bx.L.toFixed(2), _box: bx, letter: s.letter };
  });
  const want = word.replace(/\s/g, "").split("");
  const got = strokes.map((s) => s.letter);
  const missing = want.filter((c) => !got.includes(c));
  if (missing.length) throw new Error(`${word}: missing glyphs [${missing.join(",")}]`);
  perWord.push({ word, lang, strokes });
}
const freq = {};
bottoms.forEach((v) => (freq[v] = (freq[v] || 0) + 1));
const BASE_Y = +Object.entries(freq).sort((p, q) => q[1] - p[1])[0][0];

const pad = 2;
const words = perWord.map(({ word, lang, strokes }) => {
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
  strokes.forEach((s) => {
    const b = s._box;
    minx = Math.min(minx, b.minx); miny = Math.min(miny, b.miny);
    maxx = Math.max(maxx, b.maxx); maxy = Math.max(maxy, b.maxy);
  });
  const x = +(minx - pad).toFixed(2), y = +(miny - pad).toFixed(2);
  const w = +(maxx - minx + 2 * pad).toFixed(2);
  const hgt = +(BASE_Y - (miny - pad)).toFixed(2);
  const descend = +Math.max(0, maxy - BASE_Y).toFixed(2);
  return {
    text: word, lang,
    vb: [x, y, w, hgt], descend,
    aspect: +(w / hgt).toFixed(4),
    totalLen: +strokes.reduce((a, s) => a + s.len, 0).toFixed(2),
    strokes: strokes.map(({ d, t, len }) => ({ d, t, len })),
  };
});

const banner = `// GENERATED FILE — do not edit by hand (slice 37).
//
// Single-stroke cursive path data for the hero greeting. Generated offline from
// the public-domain Hershey "cursive" single-line font via 'hersheytext' — NO
// runtime font dependency; only this static path data ships. Regenerate with
// scripts/gen-hero-strokes.cjs. Each word's viewBox bottom is the baseline.

export interface HeroStroke { d: string; t: [number, number]; len: number }
export interface HeroWord {
  text: string;
  lang: string;
  /** local viewBox [x, y, w, h] — bottom edge (y+h) is the baseline */
  vb: [number, number, number, number];
  /** how far the lowest descender falls below the baseline (font units) */
  descend: number;
  /** width / height of the viewBox */
  aspect: number;
  /** sum of all stroke lengths (constant-speed pen timing) */
  totalLen: number;
  strokes: HeroStroke[];
}

/** Shared baseline (font units) — the viewBox bottom of every word. */
export const BASE_Y = ${BASE_Y};

/** Rendered em per font unit (scales the word to the headline cap height). */
export const EM_PER_UNIT = ${EM_PER_UNIT};

/** Pen stroke width in font units (scales with the word; marker weight). */
export const STROKE_UNITS = ${STROKE_UNITS};

export const HERO_WORDS: HeroWord[] = `;

process.stdout.write(banner + JSON.stringify(words, null, 1) + ";\n");
