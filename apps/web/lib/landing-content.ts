// Landing-page content (spec §20 landing). Kept out of the page component so it's
// editable and testable. The greetings span many languages/scripts to represent the
// app's multilingual reach; the SRS tiers mirror the app's real stages; the
// testimonials are SAMPLE copy (see the note below) — replace before launch.

export interface Greeting {
  text: string;
  lang: string;
}

/** Hellos from around the world — the rotating hero word + the marquee strip. */
export const GREETINGS: Greeting[] = [
  { text: "hola", lang: "español" },
  { text: "kumusta", lang: "tagalog" },
  { text: "hello", lang: "english" },
  { text: "bonjour", lang: "français" },
  { text: "olá", lang: "português" },
  { text: "ciao", lang: "italiano" },
  { text: "hallo", lang: "deutsch" },
  { text: "こんにちは", lang: "日本語" },
  { text: "안녕하세요", lang: "한국어" },
  { text: "你好", lang: "中文" },
  { text: "नमस्ते", lang: "हिन्दी" },
  { text: "مرحبا", lang: "العربية" },
  { text: "привет", lang: "русский" },
  { text: "γεια", lang: "ελληνικά" },
  { text: "merhaba", lang: "türkçe" },
  { text: "xin chào", lang: "tiếng việt" },
  { text: "สวัสดี", lang: "ไทย" },
  { text: "jambo", lang: "kiswahili" },
];

export interface SrsStage {
  name: string;
  blurb: string;
}

/** The app's real SRS tiers (§10), shown as a climbing path. */
export const SRS_STAGES: SrsStage[] = [
  { name: "beginner", blurb: "brand new — reviewed in hours" },
  { name: "familiar", blurb: "sticking now — reviewed in weeks" },
  { name: "intermediate", blurb: "solid — a month between reviews" },
  { name: "advanced", blurb: "second nature — months apart" },
  { name: "fluent", blurb: "yours for good" },
];

export interface PracticeFeature {
  icon: string;
  title: string;
  blurb: string;
}

/** The practice surfaces (§7), each a card that reveals on scroll. */
export const PRACTICE_FEATURES: PracticeFeature[] = [
  { icon: "🎧", title: "listening", blurb: "catch the words as a native voice speaks them." },
  { icon: "🎙️", title: "speaking", blurb: "say it out loud and hear how close you got." },
  { icon: "📖", title: "reading", blurb: "short stories you can annotate and dissect." },
  { icon: "✍️", title: "writing", blurb: "a daily prompt and a private journal that's all yours." },
  { icon: "🧩", title: "sentence structure", blurb: "build sentences block by block, then type them." },
  { icon: "🔀", title: "verb conjugation", blurb: "every tense, drilled until it's automatic." },
  { icon: "📝", title: "testing", blurb: "cefr, app, and real-life scenario challenges." },
  { icon: "🔁", title: "reviews", blurb: "spaced repetition keeps all of it fresh." },
];

export interface Testimonial {
  name: string;
  role: string;
  quote: string;
}

// NOTE: SAMPLE / PLACEHOLDER testimonials for layout only — not real users.
// Replace with genuine, consented testimonials before launch.
export const TESTIMONIALS: Testimonial[] = [
  {
    name: "Marisol",
    role: "on level 7",
    quote: "the reviews show up right when i'm about to forget a word. it feels like the app knows my brain.",
  },
  {
    name: "Devin",
    role: "learning tagalog",
    quote: "i've bounced off other apps, but the cozy pace and the little intermissions actually keep me coming back.",
  },
  {
    name: "Aitana",
    role: "beta tester",
    quote: "speaking practice was the piece i was missing everywhere else. now i actually say things out loud.",
  },
];
