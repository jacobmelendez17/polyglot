# Polyglot — Pre-Implementation Planning Package

Spanish/Tagalog SRS language-learning platform. Latin America-inspired design.
This document covers deliverables 1–9. Deliverable 10 (design prototypes) is in `design-options/`.

**Status: NO IMPLEMENTATION CODE YET.** This is the plan to approve/amend before Phase 1 begins.

---

## 0. Curriculum Data Audit (what your CSVs actually contain)

Before architecture, here is what I verified in the uploaded files, because several spec claims depend on them:

| Finding | Detail | Impact |
|---|---|---|
| ✅ Vocab structure | 468 items, Levels 1–10, 12 words × 4 batches per level | Matches "48 vocab per level" |
| ⚠️ Level 6 vocab | Only 3 batches (36 words) — Batch 4 missing | Level 6 can't meet the 48-word spec |
| ⚠️ Grammar coverage | 59 points, Levels 1–5 only (Level 4 has 11, not 12) | Levels 6–10 have zero grammar; unlock rule "Familiar 1 on all grammar" is trivially true there |
| ⚠️ Grammar has no Batch column | Vocab has Level+Batch; grammar has Level only | Dispersal algorithm must assign grammar→lesson itself (proposed below) |
| ⚠️ Missing enrichment | Most rows lack Pronunciation, IPA, PoS, Meaning, Examples, accepted/rejected answers | Items can be seeded as `draft`, not `published`; admin UI must support bulk enrichment |
| ⚠️ Feature-unlock mapping absent | Spec §7 says "The CSV will outline when these features become unlocked" — neither CSV contains this | Filler decision below (R-07) |
| ⚠️ Content errors | `nunca` translated "always" (should be "never"); `qué`/`que` glosses appear swapped ("that"/"what") | Import tool should flag, not silently fix |
| ⚠️ Tagalog | No Tagalog data present | Schema is multilingual-ready; Tagalog seeds deferred |

**Import strategy:** a versioned, idempotent CSV importer (admin-triggered) that maps rows → `vocabulary_items` / `grammar_points` in `draft` state, records an import report (row, warnings, errors), and never overwrites admin-edited fields without confirmation.

---

## 1. System Architecture Overview

```
                        ┌────────────────────────────────────────┐
                        │              Cloudflare                │
                        │   DNS · CDN · WAF · Rate limiting      │
                        └──────┬─────────────────────┬───────────┘
                               │                     │
              ┌────────────────▼──────┐   ┌──────────▼─────────────┐
              │  Next.js (App Router) │   │   Python API (FastAPI) │
              │  Cloudflare Pages/    │   │   Fly.io (MVP target)  │
              │  Workers (OpenNext)   │   │   Docker container     │
              │  · UI / SSR / RSC     │   │   · SRS engine         │
              │  · Auth.js (issuer)   │   │   · Answer checking    │
              │  · BFF proxy to API   │   │   · Queue builder      │
              └───────┬───────────────┘   │   · Admin/content API  │
                      │  JWT (short-lived)│   · XP/points ledger   │
                      └──────────────────►│   · Import jobs        │
                                          └───┬──────────┬────────┘
                                              │          │
                              ┌───────────────▼──┐   ┌───▼──────────────┐
                              │ Supabase Postgres│   │ Supabase Storage │
                              │ SQLAlchemy +     │   │ audio/images     │
                              │ Alembic          │   │ (naming per §33) │
                              └──────────────────┘   └──────────────────┘
                                              │
                                   ┌──────────▼─────────┐
                                   │  Upstash Redis     │
                                   │  rate limits ·     │
                                   │  idempotency keys ·│
                                   │  session cache     │
                                   └────────────────────┘

Observability: Sentry (FE+BE) · structured JSON logs · /healthz · Plausible analytics
```

**Key decisions and rationale**

1. **Next.js is a thin BFF, Python owns business logic.** All SRS math, answer normalization, queue ordering, XP awards live in the Python API as pure, deterministic functions (unit-testable without DB). Next.js never computes correctness or XP.
2. **Auth.js issues; FastAPI verifies.** Auth.js (in Next.js) handles OAuth/credentials against Supabase `auth.users`-compatible identity, issues short-lived JWTs (RS256/EdDSA, JWKS published by the Next app). FastAPI verifies signature + claims on every request. Refresh sessions live server-side in Postgres (`auth_sessions`). Details in §4.
3. **Server-authoritative progress.** The client submits answers; the server grades, applies SRS, awards XP, and returns results. The client never posts "I got it right."
4. **Idempotency everywhere it matters.** Every review/practice submission carries a client-generated `idempotency_key` (UUID). Redis SETNX + a unique DB constraint make replays a no-op returning the original result.
5. **Provider abstractions** for TTS/speech-scoring (`AudioProvider`, `SpeechScoreProvider` interfaces) so browser-native → third-party swap is a config change.
6. **Docker Compose locally** (web + api + postgres + redis + mailpit) mirrors production topology. Kubernetes explicitly deferred.
7. **Monorepo** (`apps/web`, `apps/api`, `packages/shared-types`) with generated OpenAPI → TypeScript client so FE/BE contracts can't drift.

---

## 2. Database Schema

Postgres. All tables: `id UUID PK DEFAULT gen_random_uuid()`, `created_at`, `updated_at`. Soft-deletable content tables add `deleted_at`, `deleted_by`. Content tables add `status ENUM(draft, in_review, published, archived)`. FKs `ON DELETE RESTRICT` unless noted.

### Identity & account

```sql
users              -- mirrors/extends Supabase auth.users
  id, auth_provider_id UNIQUE, email UNIQUE, email_verified_at,
  role ENUM(user, beta_tester, moderator, content_editor, admin, owner),
  status ENUM(active, suspended, deleted), last_seen_at

auth_sessions      -- server-side refresh sessions
  id, user_id FK, refresh_token_hash UNIQUE, user_agent, ip_hash,
  expires_at, revoked_at, rotated_from_session_id NULLABLE FK

profiles
  user_id PK/FK, display_name, avatar_asset_id FK NULL, bio,
  xp_total BIGINT DEFAULT 0, points_balance BIGINT DEFAULT 0,
  rank_level INT GENERATED/derived, streak_current INT, streak_best INT,
  streak_type ENUM(reviews, lessons, journal, verb_conjugation, any),
  timezone TEXT, onboarding_completed_at, immersion_unlocked_at

user_settings
  user_id PK/FK, theme ENUM(light,dark,system), font_size, color_theme,
  lesson_batch_size INT DEFAULT 5,
  review_order ENUM(newest_first, stage_order, random) DEFAULT random,
  curriculum_mode ENUM(default_dispersed, grammar_batch, fully_dispersed),
  back_to_back BOOLEAN, back_to_back_order ENUM(es_first, en_first),
  show_srs_indicator BOOLEAN DEFAULT true,
  leech_threshold NUMERIC DEFAULT 1.0,
  review_batch_enabled BOOLEAN DEFAULT true, review_batch_size INT DEFAULT 20,
  reveal_full_answer BOOLEAN, allow_cheating BOOLEAN, allow_skipping BOOLEAN DEFAULT false,
  undo_enabled BOOLEAN DEFAULT true,
  accept_user_synonyms BOOLEAN DEFAULT false,
  intermissions_enabled BOOLEAN DEFAULT true,
  immersion_mode BOOLEAN DEFAULT false,
  dialect ENUM(latam_mx, castilian) DEFAULT latam_mx
```

### Curriculum

```sql
languages
  id, code TEXT UNIQUE ('es-MX','tl','es-ES'), name, native_name,
  stage_names JSONB  -- ["Uno","Dos","Tres","Cuatro","Cinco"] per §10

modules            -- a.k.a. "levels" (spec §5: 'module' == 'level')
  id, language_id FK, position INT, title, description, status,
  UNIQUE(language_id, position)

lessons
  id, module_id FK, position INT,               -- 1..5
  kind ENUM(themed_vocab, grammar_batch, mixed),
  theme_title, status, UNIQUE(module_id, position)

lesson_items       -- ordered join; supports all curriculum modes
  id, lesson_id FK, position INT,
  item_type ENUM(vocabulary, grammar), item_id UUID,
  curriculum_mode ENUM(...),      -- which mode this placement belongs to
  UNIQUE(lesson_id, curriculum_mode, position)

vocabulary_items
  id, language_id FK, module_id FK, term, normalized_term,
  primary_translation, part_of_speech, difficulty_rank INT,
  pronunciation, ipa, meaning TEXT, context JSONB,   -- phrase-use groups per §6
  grammatical_gender ENUM(masculine,feminine,both,neutral,none) DEFAULT none,
  article ENUM(el,la,los,las,un,una,none) DEFAULT none,  -- nouns only (enforced: article≠none ⇒ PoS=noun)
  accepted_answers JSONB,   -- private: [{text, normalized, note}]
  rejected_answers JSONB,   -- private
  synonyms JSONB, variations JSONB,
  castilian_variant, latam_variant,
  audio_asset_id FK NULL,   -- audio optional per §6
  status, source_import_id FK NULL

grammar_points
  id, language_id FK, module_id FK, title, translation, structure_pattern,
  part_of_speech, meaning, explanation_rich TEXT,
  accepted_answers JSONB, rejected_answers JSONB, synonyms JSONB,
  unlocks JSONB,            -- e.g. tenses that gate verb-conjugation practice
  audio_asset_id FK NULL, status, source_import_id FK NULL

sentences          -- admin-written examples & practice sentences (§6: never scraped)
  id, language_id FK, text_es, text_en, difficulty ENUM(phrase,sentence,complex),
  audio_asset_id FK NULL, status
sentence_links     -- sentence ↔ item many-to-many, with role
  sentence_id FK, item_type, item_id, role ENUM(example, cloze, conjugation, listening),
  cloze_answer TEXT NULL, cloze_span INT4RANGE NULL

verbs_meta         -- per-verb conjugation data for §7
  vocabulary_item_id PK/FK, conjugation_class ENUM(ar,er,ir,irregular),
  is_regular BOOLEAN, conjugations JSONB  -- {tense: {person: form}}

audio_assets
  id, storage_path UNIQUE,   -- {content_type}_{content_id}_{locale}_{voice_id}_{version}.{ext}
  content_type, content_id, locale, voice_id, version INT, duration_ms,
  source ENUM(tts, human), status

user_synonyms      -- §8: user-added synonyms counted when setting enabled
  id, user_id FK, item_type, item_id, synonym, normalized, UNIQUE(user_id,item_type,item_id,normalized)
```

### Progress & reviews

```sql
user_module_state  -- curriculum mode locked at level start (§5)
  user_id, module_id, PK(user_id,module_id),
  curriculum_mode_locked ENUM(...), started_at, unlocked_at, completed_at

user_item_progress          -- SOURCE OF TRUTH per §23
  id, user_id FK, item_type ENUM(vocabulary,grammar), item_id UUID,
  srs_stage SMALLINT DEFAULT 1,        -- 1..9 (Beginner1..Fluent)
  next_review_at TIMESTAMPTZ,
  unlocked_at, lesson_completed_at, fluent_at, perfect_at,
  meaning_passed_pending BOOLEAN, reading_passed_pending BOOLEAN, -- intra-review pair state
  total_reviews INT, total_incorrect INT,
  recent_results SMALLINT[] ,          -- ring buffer, last 10 (1=correct,0=wrong) for leech calc
  leech_score NUMERIC DEFAULT 0,
  leech_state ENUM(none, watch, leech, critical) DEFAULT none,
  UNIQUE(user_id, item_type, item_id)

user_item_practice_stages   -- §10 practice stages Uno..Cinco per category
  id, user_id, item_type, item_id,
  category ENUM(sentences, listening, speaking),
  stage SMALLINT DEFAULT 0,            -- 0..5, 5 = category complete
  stage_reached_at TIMESTAMPTZ,        -- next stage available at +24h
  UNIQUE(user_id, item_type, item_id, category)

review_sessions
  id, user_id FK, kind ENUM(review, lesson_quiz, leech, weak_item),
  state ENUM(active, completed, abandoned), queue_snapshot JSONB,
  started_at, completed_at, client_resumable_until

review_answers              -- every submitted answer (§23)
  id, session_id FK, user_id FK, item_type, item_id,
  prompt_direction ENUM(es_to_en, en_to_es), prompt_kind ENUM(meaning, reading, cloze),
  submitted_answer TEXT, normalized_answer TEXT,
  original_correct BOOLEAN, final_correct BOOLEAN,
  typo_forgiven BOOLEAN, synonym_matched BOOLEAN, warning_flags JSONB,
  undo_used BOOLEAN DEFAULT false, undo_reason TEXT NULL,
  srs_stage_before SMALLINT, srs_stage_after SMALLINT NULL,  -- null until pair completes
  idempotency_key UUID UNIQUE, answered_at

srs_reviews                 -- one row per completed item-pair SRS transaction
  id, user_id, item_type, item_id, session_id FK,
  stage_before, stage_after, wrong_answer_count SMALLINT,
  promoted BOOLEAN, penalty_factor SMALLINT, occurred_at

practice_sessions
  id, user_id, practice_type ENUM(listening, speaking, reading_writing,
    sentence_structure, verb_conjugation, testing, journal_prompt),
  detail JSONB, state, started_at, completed_at

journal_entries
  id, user_id FK, prompt_id FK NULL, title, body TEXT, body_draft TEXT,
  archived_at NULL, visibility ENUM(private) DEFAULT private  -- community sharing later
journal_prompts
  id, language_id, text_en, text_target, active_on DATE UNIQUE  -- daily queue, rotates at fixed UTC time

xp_events                   -- append-only ledger (anti-abuse §12)
  id, user_id, amount INT, kind ENUM(grammar_lesson, vocab_lesson, grammar_review,
    vocab_review, journal, test_answer, translation_phrase, translation_sentence,
    translation_complex), source_table, source_id, idempotency_key UUID UNIQUE
points_events               -- same shape; currency ledger
```

### Platform

```sql
dashboard_widgets           -- catalog of widget types + defaults
user_widget_layouts         -- user_id, layout JSONB [{widget, x,y,w,h, config}], persisted cross-device
intermissions               -- id, module_id NULL, trigger JSONB, title, body_rich, status
user_intermission_views     -- user_id, intermission_id, viewed_at
changelog_entries           -- id, type ENUM(feature,fix,content,announcement), title, body, published_at, author_id
user_changelog_reads        -- user_id, last_read_at  (unread count derives)
feedback_tickets            -- id, user_id NULL, category, route, browser, body, screenshot_asset_id,
                            -- state ENUM(unanswered, answered), pinned BOOLEAN, email_sent_at
subscriptions               -- user_id, tier ENUM(free_beta, lifetime, monthly, annual), status,
                            -- stripe_customer_id NULL, current_period_end, canceled_at
admin_audit_logs            -- actor_id, action, target_table, target_id, before JSONB, after JSONB, ip_hash, at
content_versions            -- table_name, row_id, version INT, snapshot JSONB, changed_by, changed_at
content_imports             -- id, filename, kind, report JSONB, created_by
archived_content            -- soft-deleted rows land here logically via deleted_at; permanent delete requires owner approval:
deletion_approvals          -- id, target_table, target_id, requested_by, approved_by(owner) NULL, executed_at NULL
```

**Indexes that matter:** `user_item_progress (user_id, next_review_at) WHERE srs_stage < 9` (queue build), `review_answers (idempotency_key)`, `xp_events (idempotency_key)`, `lesson_items (lesson_id, curriculum_mode, position)`, GIN on JSONB answer fields for admin search.

---

## 3. API Route List (FastAPI, `/api/v1`)

Conventions: Bearer JWT required unless marked public. Zod (FE) + Pydantic (BE) validation on every body/query. Errors: `{error: {code, message, field_errors?}}`. Cursor pagination: `?cursor=&limit=`. Idempotent POSTs require `Idempotency-Key` header.

**Auth/session** (Next.js/Auth.js hosts these; API only verifies)
- `POST /auth/signup` · `POST /auth/login` · `POST /auth/refresh` (rotates session) · `POST /auth/logout` (revokes) · `GET /auth/session` — public/semi-public with strict rate limits

**Profile & settings**
- `GET /me` · `PATCH /me/profile` · `GET /me/settings` · `PATCH /me/settings`
- `GET /me/stats` (XP, rank, streaks, skill balance)

**Curriculum (read)**
- `GET /languages`
- `GET /modules?language=` · `GET /modules/{id}` (lessons + user unlock state)
- `GET /lessons/{id}` (items in user's locked curriculum mode)
- `GET /vocabulary/{id}` · `GET /grammar/{id}` (public fields only — accepted/rejected answers NEVER serialized to non-admin)
- `POST /me/modules/{id}/start` (locks curriculum mode for that level)

**Lessons**
- `POST /lessons/{id}/start` → lesson session
- `POST /lesson-sessions/{id}/answers` (idempotent) → grading result
- `POST /lesson-sessions/{id}/complete` → XP award, unlock items into SRS

**Reviews & SRS**
- `GET /me/reviews/queue?limit=` → ordered queue respecting §11 pairing distance
- `POST /review-sessions` · `GET /review-sessions/{id}` (resume support)
- `POST /review-sessions/{id}/answers` (idempotent) → `{original_correct, final_correct, warnings, srs: {before, after|null, pending_pair}}`
- `POST /review-answers/{id}/undo` → override per §9 (stores reason; no XP/SRS/leech effect)
- `POST /review-sessions/{id}/complete` · `POST /review-sessions/{id}/abandon` (persists only pair-completed SRS changes per §10)
- `GET /me/reviews/forecast?window=day|week`
- `GET /me/reviews/history?cursor=`
- `GET /me/items/{type}/{id}/progress` (SRS + practice stages + leech)

**Practice**
- `GET /me/practice/availability` (feature unlock map per level)
- `POST /practice-sessions` (type + params) · `POST /practice-sessions/{id}/answers` (idempotent) · `POST /practice-sessions/{id}/complete`
- `GET /me/leeches` · `POST /practice-sessions/leech` · `GET /me/weak-items`
- Verb conjugation: `GET /verbs/{vocab_id}/conjugations` (published only) · practice via generic practice-session endpoints

**Journal**
- `GET /journal/prompt/today` · `GET /me/journal?cursor=` · `POST /me/journal` · `PATCH /me/journal/{id}` (draft autosave) · `POST /me/journal/{id}/archive`

**Dashboard**
- `GET /me/dashboard/layout` · `PUT /me/dashboard/layout`
- `GET /me/dashboard/widgets/{widget}/data` (heatmap, line chart, forecast, skill balance…)

**Intermissions & changelog**
- `GET /me/intermissions/pending` · `POST /me/intermissions/{id}/viewed` · `GET /me/intermissions/history`
- `GET /changelog?cursor=` (public) · `GET /me/changelog/unread-count` · `POST /me/changelog/mark-read`

**Support**
- `POST /feedback` (rate-limited; triggers email to owner) — public-ish (captcha if anon)

**Admin (`/admin/*` — role-gated server-side, all actions audit-logged)**
- CRUD + state transitions (draft→in_review→published→archived) for: `vocabulary`, `grammar`, `sentences`, `audio`, `intermissions`, `changelog`, `journal-prompts`, `modules`, `lessons`
- `POST /admin/imports/curriculum` (CSV) · `GET /admin/imports/{id}`
- `GET /admin/feedback?state=` · `PATCH /admin/feedback/{id}` (answer/pin)
- `GET /admin/users` · `PATCH /admin/users/{id}/role` (owner/admin only)
- `GET /admin/archives` · `POST /admin/archives/{id}/request-permanent-delete` · `POST /admin/deletion-approvals/{id}/approve` (owner only)
- `GET /admin/audit-logs?cursor=`
- `GET /healthz` (public, no auth) · `GET /admin/jobs/failed`

---

## 4. Auth & Authorization Strategy

**Identity:** Supabase `auth.users` is the identity store; Auth.js in Next.js drives sign-in flows (email+password, OAuth later) and writes to it. A `users` row mirrors each identity with our role/status.

**Tokens:**
- **Access token:** JWT, 10-minute TTL, asymmetric signing; claims: `sub`, `role`, `sid` (session id), `iat/exp/aud/iss`. Sent as `Authorization: Bearer` from the Next BFF to FastAPI. FastAPI verifies via cached JWKS — no DB hit on the hot path.
- **Refresh session:** opaque token in a `Secure; HttpOnly; SameSite=Lax` cookie, hash stored in `auth_sessions`. Rotation on every refresh; reuse of a rotated token revokes the whole chain (theft detection). Logout revokes server-side.
- **CSRF:** double-submit token on all cookie-authenticated mutating routes in the Next app; the FastAPI surface is bearer-only (no CSRF exposure).

**Authorization:**
- Role hierarchy: `user < beta_tester < moderator < content_editor < admin < owner` — but permissions are **capability-based**, not strictly hierarchical (a moderator can manage forums but NOT edit curriculum; content_editor edits curriculum but cannot touch users). Central `require(capability)` dependency in FastAPI; capabilities mapped from role in one module (single source of truth, unit-tested).
- Row-level: every `/me/*` query filters by `user_id = token.sub` in the repository layer — never trusts client-supplied user ids.
- Admin mutations: capability check + audit log write in the same transaction. Destructive = soft delete; permanent delete requires an approval row created by requester and approved by `owner`.
- Subscription gates: middleware resolves `entitlements` (free level-1 access vs paid) once per request; Level 1 content free for all, everything else gated when billing ships. Beta users flagged `free_beta` bypass gates.

**JWT verification in Python:** `PyJWT` + JWKS cache with kid-based rotation; clock skew tolerance 30s; `aud`/`iss` enforced.

---

## 5. SRS Algorithm Specification (deterministic, unit-testable)

### 5.1 Stages and intervals

| # | Stage | Interval to next |
|---|---|---|
| 1 | Beginner 1 | 4 h |
| 2 | Beginner 2 | 8 h |
| 3 | Beginner 3 | 1 d |
| 4 | Beginner 4 | 2 d |
| 5 | Familiar 1 | 1 wk |
| 6 | Familiar 2 | 2 wk |
| 7 | Intermediate | 1 mo (30 d) |
| 8 | Advanced | 4 mo (120 d) |
| 9 | Fluent | — (out of queue) |

`INTERVALS = {1: 4h, 2: 8h, 3: 24h, 4: 48h, 5: 168h, 6: 336h, 7: 720h, 8: 2880h}` — constants table, injected clock (`now()` passed in) so tests are deterministic.

### 5.2 Review unit = the pair

Each item review consists of **two prompts**: meaning (ES→EN) and reading (EN→ES); order randomized (or forced by back-to-back setting). Stage 1–4 prompts are direct translation; stage 5–6 use short-phrase cloze; stage 7–8 use longer-sentence cloze (both vocab and grammar).

State machine per item within a session:

```
PENDING ──answer #1──► HALF (record correctness, wrong_count += misses)
HALF    ──answer #2──► RESOLVED → apply_srs() immediately (§10: "updated
                       immediately after the second answer")
```

- `wrong_count` = total incorrect submissions across both prompts for this pair in this session (a prompt answered wrongly then correctly contributes its wrong attempts).
- **Promotion:** both prompts ultimately correct **on first attempt each** (`wrong_count == 0`) → `stage += 1` (cap 9). If `wrong_count > 0` → demotion formula.
- **Demotion (spec formula, exact):**

```python
def apply_srs(stage: int, wrong_count: int) -> int:
    if wrong_count == 0:
        return min(stage + 1, 9)
    incorrect_adjustment = ceil(wrong_count / 2)
    penalty = 1 if stage < 5 else 2        # Familiar+ = stage >= 5
    return max(1, stage - incorrect_adjustment * penalty)
```

- `next_review_at = now + INTERVALS[new_stage]` (Fluent: none). **Leech modifier:** items in `leech`/`critical` state use `interval * 0.5` ("slowed down SRS" → reviewed more often).
- **Early exit (§10):** only items that reached RESOLVED persist SRS changes; HALF/PENDING items revert (their `review_answers` rows are kept for history but flagged `pair_incomplete`).
- No skip/reveal in reviews (setting `allow_skipping` exists but defaults off and does not apply to SRS reviews for MVP).

### 5.3 Undo/override (§9)

`POST /review-answers/{id}/undo` (if `undo_enabled`): sets `final_correct = true`, `undo_used = true`, optional reason; recomputes the pair's `wrong_count` **as if that answer were correct**, and — because SRS applies at pair-resolution — if the pair already resolved, replays `apply_srs` from `stage_before` and corrects `user_item_progress` (this is what "removes the penalty" means operationally). XP, points, and leech ring-buffer are **not** modified by undo; analytics counts undo events only. Original answer + original correctness always retained.

### 5.4 Leech scoring (§13)

Maintain `recent_results` ring buffer (last 10 pair outcomes, most-recent-first weighting):

```
weights = [1.0, 0.9, 0.8, ..., 0.1]  # linear decay over 10
leech_score = Σ weights[i] * wrong_i / count(recent)
state: watch ≥ 0.8 · leech ≥ user.leech_threshold (default 1.0) · critical ≥ 1.5
```

Recomputed at pair resolution. Leech state feeds: dashboard leech card, leech practice batches, and the interval modifier above. *(Note: with 0/1 outcomes this score maxes < 1.0; see ambiguity R-05 — filler decision: count each wrong pair as `1 + 0.5·(extra wrong answers)` weighted, so scores can exceed 1.0. Flagged for your confirmation.)*

### 5.5 Practice stages (Uno→Cinco)

Per item × category (`sentences`, `listening`, `speaking`): stage 0–5, +1 per qualifying completed practice, minimum 24 h between stage-ups (`stage_reached_at + 24h` gate). All three categories at 5 **and** SRS ≥ Fluent ⇒ `perfect_at` set. Stage names localized from `languages.stage_names`.

### 5.6 Review queue construction (§11)

Deterministic given (item set, seed, settings):

1. Select due items (`next_review_at <= now`), order by user setting (newest-first / stage / random-with-seed), cap by batch size (default 20 items = 40 prompts).
2. Emit two prompts per item with **gap constraint: 0 ≤ distance ≤ 5** (distance = prompts between the pair). Back-to-back setting forces distance 0 with configured direction first.
3. Algorithm: shuffle items; place first prompts greedily; insert each second prompt at a uniform random offset `d ∈ [0,5]` after its partner, resolving collisions by shifting right while re-validating all previously placed pairs (property-tested: no pair distance ever > 5).
4. Queue snapshot stored on the session for refresh/disconnect resume.

### 5.7 Answer checking & normalization (§8) — pure function

```
normalize(s): trim · collapse spaces · lowercase · strip ¡¿!?.,; ·
              NFC → optional diacritic folding depending on mode
check(answer, item, mode, settings) → {correct, warnings[], typo_forgiven, synonym_matched}
```

Order of evaluation: rejected_answers (exact-normalized match ⇒ wrong, with targeted message) → accepted_answers/primary translation → synonyms (stored only; plus `user_synonyms` if enabled) → typo tolerance.

Typo tolerance (review "normal" mode, per your rule): pass if Damerau-Levenshtein distance ≤ 2 **and** all answer letters present modulo the swaps/omissions (i.e., transpositions or ≤2 missing letters); accents produce a **warning-pass** in normal mode, hard-fail in strict/test mode; "allow cheating" widens distance and auto-accepts synonyms generously. Missing-accept case: near-miss to a plausible alternate ⇒ accept **with warning** (default on, toggleable). Gender/number agreement checked for cloze prompts via expected-form lists on the sentence link. Every branch is table-driven → exhaustive unit tests.

### 5.8 XP (server-side only, §12)

`XP_TABLE = {grammar_lesson: 60, vocab_lesson: 50, grammar_review: 20, vocab_review: 10, journal: 500, test_correct: 20, phrase: 100, sentence: 200, complex: 300}`. Awarded in `xp_events` with idempotency keys at lesson/pair/entry completion; verified against server-graded results only. Rate limits: review submissions ≤ 1/sec sustained per user (Redis token bucket); duplicate keys return the original event.

---

## 6. Testing Strategy

**Philosophy:** all logic in §5 is pure functions in `apps/api/src/domain/` — no DB, no clock, no randomness without injection. Test-first for that layer.

**Backend (pytest)**
- Unit: `apply_srs` full matrix (every stage × wrong_count 0–8, floor/cap, penalty boundary at stage 5); interval lookup incl. leech modifier; pair state machine incl. early-exit persistence rules; undo replay; leech ring buffer + thresholds; queue builder property tests (Hypothesis: ∀ outputs, pair distance ∈ [0,5], all pairs present, back-to-back honored); normalization/typo/synonym/rejected-answer tables incl. the spec's examples (`esta`/`está`, swapped letters, 1–2 missing letters); XP table incl. the spec's worked examples (5 grammar lessons = 300, mixed lesson = 320, 30+3 reviews = 630); curriculum dispersal generator (each mode yields 48 vocab + 12 grammar per level, no duplicates); unlock rule (all grammar Familiar-1 + ≥ 36/48 vocab).
- Integration (pytest + testcontainers Postgres/Redis): auth-protected routes reject anon/expired/wrong-audience; role/capability matrix per admin route; lesson completion → item unlock → first reviews scheduled; review submission idempotency (same key twice = one `xp_events` row); session resume; soft delete + owner-approval flow; CSV importer against the real uploaded files (fixtures) incl. warning report.
- Migration checks: `alembic upgrade head && downgrade -1 && upgrade head` in CI against a scratch DB.

**Frontend**
- Jest + React Testing Library: review input (states: loading/empty/success/error, warning banners, undo button), dashboard widgets with mocked data, settings form validation, lesson card, forecast rendering.
- Playwright E2E: signup→onboarding→skip; lesson start→complete→XP toast; full review session incl. one wrong answer + undo; settings change persisting; refresh mid-review-session resumes; admin creates + publishes a vocab item; a11y smoke (axe) + keyboard-only review session.

**CI (GitHub Actions):** lint (ruff, eslint) → typecheck (mypy, tsc) → backend unit → backend integration → frontend unit → build → Playwright → migration check. Any failure blocks deploy. Seed script (`seed_demo.py`, clearly marked demo data) runs in E2E environment only.

---

## 7. Security Checklist

- [ ] Pydantic validation on every API body/query/path; Zod on every FE form + BFF proxy
- [ ] Accepted/rejected answers excluded from all non-admin serializers (test asserting this)
- [ ] Parameterized queries only (SQLAlchemy; no raw string SQL; lint rule)
- [ ] Output escaping by default; user rich text (journal, future forums) sanitized server-side (bleach/allow-list) and rendered without `dangerouslySetInnerHTML` except sanitized paths
- [ ] AuthN: JWT signature/exp/aud/iss verified; JWKS rotation supported; 30s skew max
- [ ] Refresh rotation with reuse-detection revocation; sessions revocable (logout-all)
- [ ] Cookies: `Secure`, `HttpOnly`, `SameSite=Lax`; CSRF double-submit on cookie-auth mutations
- [ ] Server-side capability checks on every admin/content route (no UI-hiding-only); tested matrix
- [ ] Rate limits (Upstash + Cloudflare WAF rules): auth 5/min/IP, review submissions 60/min/user, feedback 3/hour, future forum posts
- [ ] Idempotency keys on all XP/points/review/practice mutations; unique constraints as backstop
- [ ] XP/points computed server-side only; ledgers append-only; anomaly alert on outlier rates
- [ ] Secrets in env only (Fly secrets / CF bindings); no secrets in repo; `.env.example` documented
- [ ] Logs structured, PII-scrubbed: no tokens, passwords, journal bodies, or answer contents at info level
- [ ] Supabase Storage: private buckets; audio served via short-lived signed URLs
- [ ] Voice recordings processed in memory / temp only, never persisted (test + code review gate)
- [ ] Admin audit log written transactionally with every admin mutation
- [ ] Soft delete default; permanent delete requires owner approval record
- [ ] Security headers via Next middleware: CSP (nonce-based), HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- [ ] Dependency scanning (Dependabot + `pip-audit`/`npm audit`) in CI
- [ ] Health endpoint exposes no version/config detail
- [ ] Backups: Supabase automated (MVP) → PITR (paid prod); separate scheduled Storage mirror; documented restore drill once per quarter

---

## 8. MVP Implementation Phases

Your five phases, sequenced into shippable slices (each slice meets the Definition of Done before moving on):

**Phase 1 — Foundation** *(slices: 1a repo/CI/Docker-Compose/healthz → 1b schema+migrations+seed → 1c auth end-to-end → 1d app shell/nav/settings → 1e admin skeleton + CSV importer + roles)*
Exit: user can sign up, log in, see empty dashboard; admin can import your CSVs and browse content in draft state; CI green.

**Phase 2 — Curriculum + SRS** *(2a curriculum modes + level locking → 2b lesson flow → 2c answer-checking engine [pure, fully tested first] → 2d review queue + sessions + pair SRS → 2e undo, history, forecast card)*
Exit: full learn→review loop on Level 1 with deterministic tests for every §5 rule.

**Phase 3 — Practice** *(3a sentence structure: cloze + blocks + full translation → 3b verb conjugation lessons/tiles → 3c listening via TTS provider abstraction → 3d weak-item + leech batches → 3e practice stages Uno–Cinco + Perfect status)*

**Phase 4 — Polish** *(4a onboarding slides incl. gag interactions + a11y alternatives → 4b guided tour → 4c widget customization/persistence → 4d intermissions → 4e immersion mode (UI strings only) → 4f changelog)*

**Phase 5 — Monetization/Community** *(Stripe + gates → read-only forums → moderation → support upgrades)*

Ordering rationale: the answer-checker and SRS engine are built before any UI consumes them so the riskiest logic is test-hardened earliest; the importer lands in Phase 1 so real content exists for every later phase; TTS/speech remain behind provider interfaces so Phase 3 doesn't block on vendor choice.

---

## 9. Risks, Assumptions & Ambiguities (need your answers; filler decisions marked ⚙)

| # | Item | Detail | ⚙ Filler decision (changeable) |
|---|---|---|---|
| R-01 | Level 6 vocab batch 4 missing | 36/48 words | Import as-is; unlock rule uses ¾ of *actual* item count |
| R-02 | Grammar for Levels 6–10 missing | Unlock rule degenerates | Levels 6–10 unlock on vocab-only rule until content exists |
| R-03 | Grammar has no batch column | Dispersal needs deterministic placement | Round-robin grammar into lessons by CSV order: 3 per themed lesson (default mode) |
| R-04 | `nunca`="always", `qué`/`que` glosses look swapped | Content correctness | Importer flags warnings; admin fixes in UI; no silent correction |
| R-05 | Leech formula can't exceed 1.0 with 0/1 outcomes but thresholds go to 1.5 | Math gap in spec | Weighted wrongs can exceed 1 per review (extra wrong answers add 0.5 each) |
| R-06 | "Both right to level up" vs "wrong answers demote" — what if meaning right, reading wrong then right? | Promotion requires zero wrong attempts? | Yes: any wrong attempt in the pair ⇒ demotion formula (wrong_count ≥ 1) |
| R-07 | Practice-feature unlock map "in the CSV" — absent | §7 gating undefined | Placeholder map: sentence structure @ L1 complete, listening @ L2, reading @ L2, verb conjugation @ tense-grammar Familiar-1, testing @ L3, speaking post-MVP |
| R-08 | "¾ of the vocabulary" rounding | 36/48 exact; odd counts? | `ceil(0.75 × count)` |
| R-09 | Curriculum option 3 "almost random" | Needs determinism | Seeded shuffle per (user, level) so refresh doesn't reshuffle |
| R-10 | Undo "removes the penalty" vs "doesn't affect SRS stage" (§9 internal tension) | Interpreted: undo corrects the *grading* (and thus the SRS outcome derived from it) but never grants XP/points nor edits leech buffer | Confirm |
| R-11 | Daily prompt rollover time | "same time every 24h" | 00:00 UTC; user-timezone display |
| R-12 | Tagalog counting names for practice stages | Need Isa–Lima etc. | Stored per-language in `languages.stage_names` |
| R-13 | Speech scoring vendor | Cost/privacy unknown | MVP: browser SpeechRecognition behind `SpeechScoreProvider`; vendor eval in Phase 3 |
| R-14 | Auth.js × Supabase auth.users coupling | Two auth brains risk drift | Auth.js is the only writer; Supabase used as identity store + RLS-free (API is the gate) |
| R-15 | Token-budget pressure ("beat the race") | Quality vs speed | Slice-based delivery above; each slice independently shippable |
| R-16 | Audio production cost | TTS vs human | MVP: curated TTS, stored per §33 naming; human recordings later via same asset table |
| R-17 | "Module" vs "level" vs "rank" terminology | Confusable in UI | Codebase says `module`; UI says "Level"; XP tier says "Rank" everywhere |

---

## 10. Design Prototypes

Three interactive HTML mockups in `design-options/` (open in a browser, screenshot at will). Each shows the landing hero **plus** a dashboard/review-card strip so you can judge real components, and each respects `prefers-reduced-motion`.

- **Option A — “Fiesta Brutalism”** (`option-a-fiesta.html`): the closest evolution of your KaniCompanion look — cream paper, chunky outlines, hard offset shadows — re-grounded in a Mexican palette (rosa mexicano, marigold, cactus green) with a papel picado banner as the signature element.
- **Option B — “Ruta del Sol”** (`option-b-ruta.html`): travel-journal direction; sunset gradient, winding journey path as the hero (mirrors your Journey Card), stamp/postcard SRS badges.
- **Option C — “Talavera”** (`option-c-talavera.html`): calmer, premium; deep cobalt talavera-tile motifs, white ceramic cards, saffron accents — reads more "paid product," less playful.

My recommendation: **A for brand energy with B's journey-path adopted as the dashboard Journey Card.** All three share one token system so mixing is cheap.

---

## 10b. Design Decision Record (2026-07-11)

**Chosen: “Terraza” cozy direction** (see `design-options/cozy/cozy-3-terraza.html`).
Adobe cream background with grid-paper texture, dusty-teal primary, blush/marigold accents,
Shantell Sans lowercase UI with wide tracking, Lora italic empty states, pill tabs,
dashed dividers. Tokens locked in `packages/design-tokens/terraza.{css,json}` — all UI
derives from these; no ad-hoc colors.

---

## Slice 1b — Database Schema, Migration, Importer (completed 2026-07-12)

**Delivered**
- 38 SQLAlchemy tables across `identity`, `curriculum`, `progress`, `platform`
  modules; UUID PKs, timestamps, content status + soft delete, and a DB-level
  CHECK constraint enforcing "only nouns carry articles" (§6).
- Alembic initial migration, verified **reversible** on Postgres 16 (3 full
  up/down cycles) with **zero model↔migration drift**. Enum types are created
  once and dropped in `downgrade()` (fixes the classic re-upgrade collision).
- Pure, testable CSV importer (`app/importer/curriculum_csv.py`) + idempotent
  DB import service. Imports content as **draft**; never publishes, never guesses
  articles/gender, never auto-corrects suspect content — it flags.
- Seed data (owner user, es-MX + tl languages with stage names, 14-widget catalog).
- 19 tests pass, including runs against the **real uploaded CSVs**.

**Confirmed data findings (supersede the §0 estimates):**
| Finding | Verified value |
|---|---|
| Vocab rows in CSV | 468 |
| Rows with a hard error | 1 — row 41 `nosotros` has no translation |
| In-level duplicates (merged + flagged) | 2 — `el martes` @L3, `algo` @L10 |
| Distinct vocab items imported | 465 |
| Level 1 count | 47 (one row dropped for the error above) |
| Level 6 count | 36 (batch 4 absent) |
| Grammar points | 59 across L1–L5 (L4 has 11) |
| Untranslated / term==translation rows | 0 (data cleaner than first audit suggested) |
| `nunca`="always" issue | not present in this CSV (suspect-flag mechanism retained for future) |

**Notable:** DB-backed tests use `pgserver` (bundled Postgres), so the suite —
and CI — exercises real Postgres, enums, and constraints **without Docker**.
This also means your Mac can run the backend tests even before Docker Desktop
finishes installing: `cd apps/api && pip install ".[dev]" && pytest`.

**Next — slice 1c:** Auth.js in Next.js issuing short-lived JWTs, FastAPI JWKS
verification, refresh-session rotation, and the capability/role authorization layer.

---

## Slice 1c — Authentication & Authorization (completed 2026-07-13)

**Delivered (backend-first; Auth.js in Next.js layers on top later):**
- Password hashing: PBKDF2-HMAC-SHA256 (stdlib, no external dep), salted, self-describing
  format with opportunistic rehash. Constant-time verify.
- Tokens: short-lived HS256 access JWT (10 min) verified at one point (`verify_access_token`
  enforces sig/exp/aud/iss + 30s skew); opaque 256-bit refresh token, only its SHA-256 hash
  stored server-side.
- Sessions: refresh rotation on every use; reuse of a rotated/revoked token revokes the whole
  session chain (theft detection). Logout + logout-all revoke server-side, so a stolen access
  token dies within its short TTL because the session check fails.
- Capability-based authorization (`app/auth/capabilities.py`): explicit, NON-hierarchical
  role→capability map. content_editor edits curriculum but can't manage users; moderator
  moderates forums but can't edit curriculum; only owner approves permanent deletes.
- Endpoints: `POST /api/v1/auth/{signup,login,refresh,logout}` + `GET /api/v1/auth/me`.
  Uniform "invalid email or password" (no user enumeration); consistent error shape.
- FastAPI deps: `get_current_user` (bearer → verify → session-alive → user) and
  `require(capability)` gate returning 403.
- Migration `99fd287fec7c`: adds `users.password_hash` + makes session times tz-aware.
  Verified reversible; zero drift.

**Tests: 45 passing** (was 19). New: password hashing, capability matrix, token
sig/exp/aud round-trips, and full DB+API flow — signup, duplicate rejection, wrong-password
401, refresh rotation, **reuse-detection chain revocation**, logout killing access, and
capability gates (user forbidden / content_editor allowed).

**Security note:** MVP uses HS256 with a server secret (`AUTH_SECRET` env var; the default is
a dev placeholder and MUST be overridden in production). The plan's RS256/JWKS path (Auth.js as
issuer) swaps in at `verify_access_token` without touching call sites.

**Next — slice 1d:** app shell + real auth UI in Next.js (login/signup forms calling these
endpoints), protected dashboard route, and the header/nav from PLANNING §20.
