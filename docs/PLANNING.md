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

---

## Slice 1d — App Shell & Auth UI (completed 2026-07-13)

**Delivered (Next.js frontend, wired to the 1c auth API):**
- Typed API client (`lib/api.ts`) with structured error handling incl. network failures.
- Auth context (`lib/auth-context.tsx`): tokens in localStorage, session bootstrap on load,
  automatic one-shot refresh on a 401. Same `useAuth()` shape will hold when Auth.js cookies
  replace localStorage.
- Pages: `/login`, `/signup` (shared `AuthForm`), `/dashboard` (protected), and a
  session-aware `/` that redirects to dashboard or login.
- Header/nav (PLANNING §20): logo → dashboard, levels/practice links, account dropdown with
  profile/settings/logout, and an **admin item gated on the `admin_panel` capability**.
- `Protected` route guard: gentle loading state while auth bootstraps, redirect to /login if
  unauthenticated.
- Dashboard widget shells in the Terraza style (welcome, progression, next lesson, reviews,
  streak, forecast) with honest empty states — no fake progress data.
- Terraza UI primitives (Card/Input/Button/Label/FormError) all derived from the design tokens.
- Fonts made resilient: `display:"swap"` + system fallbacks so a Google Fonts hiccup never
  blocks the build or first paint.

**Docker: the full stack now runs with one command.**
- API `entrypoint.sh` runs `alembic upgrade head` + seed before starting uvicorn, so a fresh
  `docker compose up` yields a migrated, seeded database automatically.
- `docker-compose.yml` passes `NEXT_PUBLIC_API_URL` to the web container; runtime API image is
  slimmed (no test toolchain).

**Tests:** frontend 3 passing (API client success/401/network), backend still 45. Production
`next build` verified (all 5 routes compile). typecheck + ruff clean.

**Next — slice 1e:** admin skeleton + CSV import UI + user/role management, then Phase 1 closes.

---

## Slice 1e — Admin Panel, Landing Page, Richer Signup (completed 2026-07-13)

**Delivered:**
- **Landing page** (`/`): public front door in Terraza style — hero, feature cards,
  how-it-works, closing CTA. Signed-in visitors auto-redirect to their dashboard.
  (Added to Phase 1 by request; was previously implied for Phase 4.)
- **Signup now collects name + confirm password** (§by request): `SignupRequest` gains
  `name`; the service stores it as the profile display_name; `/me` returns it; the
  dashboard greets by real name. Frontend form validates name presence, 8-char minimum,
  and password match before submitting.
- **Admin API** (all capability-gated + audit-logged, §22):
  - `POST /admin/imports/{vocabulary,grammar}` — multipart CSV upload → importer →
    draft rows + a persisted ContentImport report. 5 MB cap, UTF-8 (BOM-tolerant).
  - `GET /admin/content/{vocabulary,grammar}` — paginated, filter by level/status.
  - `PATCH /admin/content/.../status` — draft→in_review→published→archived.
  - `GET /admin/users`, `PATCH /admin/users/{id}/role` — with the rule that only an
    owner may grant or revoke the owner role.
- **Admin panel UI** (`/admin`, gated on `admin_panel` capability): CSV import with the
  full validation report rendered (errors + collapsible warnings), content browser with
  one-click publish, and user role management. Non-admins are redirected away.

**Tests: 52 backend** (was 45) — import authorization, real-CSV import as content_editor
(465 created, 1 error surfaced), audit-log writes, list+publish, user-management gating,
owner-role protection, and signup name capture. Frontend: 3 passing, all 6 routes build.

**Phase 1 is complete.** Next: **Phase 2** — the lesson flow, the SRS review engine
(the spaced-repetition scheduler from §10), and answer checking. This is where Polyglot
starts actually teaching Spanish.

---

## Slice 2 — Phase 2: Lesson Flow, SRS Engine, Answer Checking (completed 2026-07-19)

**The app now teaches Spanish.** Learn → unlock into SRS → review → schedule.

**Pure domain logic (deterministic, heavily unit-tested):**
- `domain/srs.py` — 9-stage engine. Clean pair (0 wrong) promotes +1; any wrong
  demotes by ceil(wrong/2) × penalty, where penalty is 2 at Familiar 1+ (stage ≥5),
  1 below. Floors at Beginner 1, caps at Fluent. Intervals 4h→8h→1d→2d→1wk→2wk→1mo→4mo;
  Fluent leaves the queue. Leech items review at half-interval.
- `domain/answer_check.py` — accent-sensitive with warn-pass in normal mode
  (strict/test require accents); Damerau-Levenshtein typo tolerance scaled to length
  (short words never over-forgiven); stored synonyms + rejected answers; user synonyms
  behind a setting. Never uses AI matching, only stored data.
- `domain/queue.py` — two prompts per item (meaning + reading), pair distance held to
  0–5. Validated across 50 seeds + Hypothesis property tests. Back-to-back mode honours
  the direction-order setting.
- `domain/leech.py` — weighted 10-review window, newest-heaviest; thresholds watch 0.8 /
  leech 1.0 / critical 1.5. A persistently 2-wrong item exceeds 1.0 → reaches Critical
  (**resolves R-05**).
- `domain/curriculum.py` — three modes (default_dispersed / grammar_batch /
  fully_dispersed), seed-stable so refresh never reshuffles. Level unlock uses ACTUAL
  item counts (all grammar + ≥75% vocab at Familiar 1), so Level 6's 36 words and the
  missing L6+ grammar don't wedge progression (**R-01/R-02/R-08**).

**Service + API layer:**
- `services/lessons.py`, `services/reviews.py`; routes in `api/routes/learn.py`:
  levels, lessons, lesson detail/complete, review sessions, answer submit, undo,
  session complete, and `/me/stats`. Grading and SRS transitions are server-side only.
- Idempotency everywhere: lesson completion and answer submission both take a
  client key; retries never double-award XP or double-write answers.
- Pair semantics: an item's SRS changes only when BOTH prompts are answered; early
  exit keeps resolved pairs and reverts half-finished ones.

**Frontend:**
- `/levels`, `/levels/[level]`, `/levels/[level]/lessons/[lesson]` (lesson-taking UI
  with progress bar and teaching cards), `/reviews` (full session: paired prompts,
  answer input, correct/incorrect feedback, SRS stage movement, "i was right" undo).
- Dashboard widgets wired to real `/me/stats` (reviews due, XP, progression, forecast).
- Header nav now points at /levels and /reviews.

**Requested additions delivered:**
- Dashboard greets "Welcome back, <Name>" using the signup name.
- Login page has a "← back to home" link and a "forgot your password?" link to a
  /reset-password placeholder (real flow ships with email support).

**Tests: 140 backend** (was 52) + 3 frontend. Migration round-trips, zero drift, all 11
web routes build.

### ⚠️ OPEN ISSUE for Jacob — XP spec conflict
The spec's worked example says "30 vocab reviews + 3 grammar reviews = 600 + 30 = 630",
which implies vocab_review=20 and grammar_review=10. But the spec's own XP *table* lists
grammar_review=20 and vocab_review=10 — the opposite. Those give 30×10 + 3×20 = **360**,
not 630. I implemented the **table** as the source of truth (360). If you actually want
the worked-example numbers, we flip two values in `domain/xp.py`. Flagging for your call.

**Next — Phase 3:** practice features (listening, translation, fill-in-the-blank,
conjugation, weak-item/leech practice).

---

## Slice 2.1 — Curriculum seed script + optional enrichment fields (2026-07-19)

**Curriculum seed script** (`app/db/seed_curriculum.py`): imports the bundled Spanish
CSVs (now in `app/db/seed_data/`) AND publishes them, so lessons/reviews are immediately
playable — unlike the admin import which loads drafts for review. Idempotent; `--force`
overwrites editor-touched rows, `--drafts-only` skips publishing. Verified end-to-end:
465 vocab + 59 grammar published, 10 modules published, 4 lessons form at Level 1.
  Run: `docker compose exec api python -m app.db.seed_curriculum`

**Enrichment fields are now optional.** Pronunciation, IPA, part-of-speech, and meaning
no longer emit a warning when blank — many rows legitimately omit them. Vocab import
warnings dropped from ~1,847 to 5 (only real signal now: 2 merged duplicates + 3 structural
notes about Levels 1 and 6). The genuine requirements (Translation, Level, Batch) still
error. `nosotros` (row 41) still correctly errors as it has no translation.

**Admin UI fixes:** the content list now refreshes automatically after an import (was
showing a stale "0 items"), and a "publish all in level" button publishes a whole level's
drafts at once instead of one at a time.

All 140 backend tests still pass; frontend builds.

---

## Slice 3 — WaniKani-style dashboard redesign (2026-07-19)

Reworked the dashboard around the lesson/review action pattern used by WaniKani,
BunPro, and KaniCompanion.

**Backend (`/me/stats` extended, no migration — all computed):**
- `lessons_available`: published items the user hasn't started yet.
- `stage_group_counts`: WaniKani-style SRS buckets (beginner 1-4 / familiar 5-6 /
  intermediate 7 / advanced 8 / fluent 9).
- `stage_counts`: per-stage counts (all 9 stages).
- 7-day `forecast` (was 3) + `next_review_at` when nothing is due now.

**Frontend:**
- Two large count-bearing action buttons (lessons + reviews) as the dashboard hero —
  the primary calls to action, styled in blush/teal with an oversized glyph flourish.
- Mixed-size widget grid (4-col): full-width welcome, 2-col progression breakdown with a
  stacked SRS proportion bar, small XP/fluent tiles, 2-col review-forecast bar chart,
  and a tricky-items tile. Cards fill cell height so rows align.
- Shared stats hook with a short module-level cache so the widgets make one request.
- Header nav already points at /levels and /reviews.

**Tests: 141 backend** (added lessons_available coverage) + 3 frontend. Build clean.

**Note:** kept the Terraza visual language (the app's established identity) but adopted
WaniKani's information architecture. A draggable/customizable widget layout (WaniKani's
newest feature) is deferred — this slice delivers the fixed varied-size layout.

---

## Slice 4 — Phase 3 practice (core), onboarding slides, wider dashboard (2026-07-19)

**Wider dashboard:** containers widened max-w-5xl → max-w-7xl; widget grid reworked to
6 columns for the extra space (progression 3-wide, forecast 2-wide, tiles fill the rest,
plus a new practice tile).

**Practice features** (Phase 3 core — TTS listening deferred to its own slice):
- `domain/practice.py` (pure): weak-item weighting (leeches dominate, then mistakes, then
  low stages), seed-stable selection, cloze construction (whole-word, case-insensitive,
  returns None when the term isn't in the sentence), conjugation cell lookup, and the
  Uno..Cinco practice-stage progression with Perfect status.
- `services/practice.py`: builds sessions from LEARNED items, grades with the practice-mode
  answer checker. Crucially, the expected answer is derived SERVER-SIDE per mode — the client
  never declares it. Practice awards XP and advances the practice-stage but never touches SRS.
- Routes `api/routes/practice.py`: session create / answer / complete. Three modes:
  fill_blank (cloze from linked example sentences), conjugation (from verbs_meta), weak_items.
- Frontend: `/practice` hub + `/practice/[mode]` runner (progress bar, feedback, XP tally),
  practice nav link, dashboard practice tile.

**Onboarding slides** (Phase 4, pulled forward): `/welcome` — 5-slide intro (map, SRS trail,
skills, notebook gag, ready) shown after signup. Gag is fully skippable with an accessible
plain Continue path; SVG art is decorative/aria-hidden. Signup now routes to /welcome; login
still goes straight to the dashboard.

**Tests: 161 backend** (+20: 13 practice-domain, 7 practice-flow) + 3 frontend. No migration
(practice reuses existing tables). Zero drift, all routes build.

**Deferred:** TTS listening practice (needs the SpeechScoreProvider/TTS abstraction — its own
slice), and the full practice-stage UI surfacing across all categories.

---

## Slice 5 — Practice data seed, strict level gating, post-lesson quiz (2026-07-19)

**Practice data seed** (`app/db/seed_practice.py` + `app/db/seed_data/practice_data.py`):
- 40 verb conjugation tables (present/preterite/future × 6 persons). Regular -ar/-er/-ir
  forms generated from the stem (future correctly attaches to the full infinitive);
  10 irregulars written out (ser, estar, tener, hacer, ir, querer, poder, pagar, llegar,
  contar). Verified: hablar→hablo/hablaré, comer→comí, ser→soy.
- Tags matching words `part_of_speech='verb'` — necessary because the source CSV leaves
  PoS blank on 470/480 rows, so conjugation practice previously found nothing. A naive
  "-ar/-er/-ir ending" heuristic was rejected: it misclassifies *ayer* (yesterday).
- 42 example sentences with explicit `cloze_answer` links, written against words that
  ACTUALLY exist in this curriculum (colours, adjectives, verbs, time words — the
  curriculum has few concrete nouns). Seeder skips targets not in the DB.
- Result: all three practice modes now produce content (fill_blank 42 sources,
  conjugation 34 verbs, weak_items always).
  Run: `docker compose exec api python -m app.db.seed_practice`

**Strict level gating (WaniKani/BunPro-style):** `VOCAB_UNLOCK_RATIO` 0.75 → **1.0**, and
grammar likewise. The next level stays locked until EVERY item in the previous level has
reached Familiar 1. `level_unlock_progress` now also returns percent/remaining/totals, and
`/levels` exposes `unlock_progress` so locked levels show "32/47 words · 15 to go".
⚠️ Note: WaniKani itself uses 90%, not 100%. At 100% a single stubborn leech can stall
progression indefinitely. The ratio is a named constant and a function parameter precisely
so it can be relaxed without a refactor if that becomes a problem in practice.

**Post-lesson quiz (the WaniKani gate).** Teaching an item is no longer proof of knowing it:
- `POST /levels/{n}/lessons/{m}/quiz` starts a quiz session (reuses `ReviewSession.kind
  = "lesson_quiz"`, which the schema already anticipated).
- `POST /quiz/{session}/answers` grades ONE answer server-side against the item's stored
  answers (the client never supplies the expected value).
- `complete_lesson` now only unlocks items the learner answered correctly, and reports
  `blocked_by_quiz`. Wrong answers aren't punished — they cycle to the back of the queue
  to be retried, so the quiz is a gate, not a filter.
- Frontend: the lesson page gained a quiz phase after the teaching cards, with a retry
  queue and its own progress bar.

**Tests: 170 backend** (+9: quiz gate incl. "no unlock without passing", retry-then-unlock,
server-side grading; strict-unlock incl. one-item-short still locked; unlock-progress
reporting) + 3 frontend. No migration. Zero drift.

Also fixed packaging: `packages = ["app"]` → find-packages with `package-data` for the CSVs,
so subpackages and seed data ship correctly.

---

## Slice 6 — 90% gating, lesson count scoped to unlocked levels (2026-07-21)

**Unlock threshold 100% → 90%** (`VOCAB_UNLOCK_RATIO`/`GRAMMAR_UNLOCK_RATIO` = 0.9),
matching WaniKani. 90% is the right number precisely because it stops a handful of
stubborn leeches from stalling progression indefinitely; tests cover both sides
(44/48 unlocks, 43/48 does not).

**Fixed: the dashboard advertised 509 lessons.** `lessons_available` counted every
published item in the curriculum, so the lessons button offered the entire 509-item
corpus as if it were immediately learnable. It now counts only unstarted items in levels
the user has actually UNLOCKED — level 1 only, at the start.

**Fixed: locked levels were reachable by URL.** `/levels/5/lessons` (and lesson detail,
quiz, and complete) had no server-side unlock check — the gate existed only in the UI.
All four endpoints now return 403 `level_locked`. The gate is enforced where it counts.

**Refactor:** replaced the per-level `_level_unlock_state` (one query set per level) with
`_all_level_states`, which loads modules, published item ids, and user progress once and
evaluates every level in a single pass. `/levels` and `/me/stats` now share it, so the
lesson count and the level list can't disagree.

**Frontend:** the lessons button's empty state is now context-aware — "keep reviewing to
unlock the next level" once you've learned something, rather than a bare "nothing right now".

**Tests: 175 backend** (+5: scoped lesson count, count grows on unlock, 403 on all four
locked-level endpoints, unlocked level reachable, 90% boundary cases) + 3 frontend.
No migration. Zero drift.

---

## Slice 7 — Listening practice & audio (closes Phase 3) (2026-07-22)

**Audio provider abstraction** (`domain/audio.py`, pure): `resolve_audio()` returns an
`AudioRef` in one of three modes — `stored` (a real file), `browser_tts` (synthesise
client-side), or `unavailable`. Stored assets ALWAYS win, so human recordings can replace
TTS gradually, item by item, with no code change and no migration (**resolves R-16**).
`asset_storage_path()` implements the §33 naming contract.

**MVP audio = the browser's own speech engine.** Free, keyless, no per-request cost, works
in every current browser — which is what makes listening shippable now rather than blocked
on a vendor decision (**R-13/R-16 stay open without blocking**). Adding cloud TTS later is a
new provider plus rows in `audio_assets`; no call site changes.

**Listening practice** (`/practice/listening`): hear a word, type what you heard. The
Spanish is deliberately never rendered — tests assert `shown == ""` and that typing the
English translation is graded WRONG. Autoplays once per prompt with a replay button.

**Audio everywhere else:** play buttons on lesson teaching cards, quiz prompts, and review
prompts (Spanish side only — hearing the English would give the answer away).

**Settings + migration `70e897feb3f0`:** `audio_autoplay` (default OFF — unexpected sound is
hostile), `audio_voice`, `audio_rate`. ⚠️ Alembic generated these as NOT NULL with no
server_default, which would have failed on the existing `user_settings` rows; added
`server_default` and verified by migrating a table that already had a row (backfilled
to `(False, '', 1.00)`).

**Frontend** `lib/speech.ts`: wraps `speechSynthesis` with async voice loading, LatAm/Mexican
Spanish voice preference, cancel-before-play, and graceful degradation when unsupported.

**Tests: 188 backend** (+13: 9 audio-resolution incl. stored-beats-TTS and the naming
contract, 4 listening incl. word-never-shown and English-rejected) + 3 frontend. Zero drift.

**Phase 3 is complete.** Next: slice 8 (practice stages + item detail pages) or slice 9
(guided tour + widget customization).

---

## Slice 8 — Practice stages surfaced in the UI, item detail pages (2026-07-22)

**Bug fix: listening reps were advancing the wrong category.** `_practice_category()`
mapped every practice mode to `sentences`, so listening practice never moved its own
Uno..Cinco stage — it silently fed `sentences` instead. Fixed: `listening` mode now
advances `PracticeCategory.listening`; `fill_blank`/`conjugation`/`weak_items` still
share `sentences` (there's no dedicated mode for `speaking` yet — R-13).

**24h stage gate, implemented for the first time.** PLANNING §5.5 always specified
"minimum 24h between stage-ups," but `advance_practice_stage()` had no time input and
advanced on every correct answer. It now takes `stage_reached_at`/`now`; the first-ever
advance (stage 0, `stage_reached_at is None`) is never gated, matching the existing
`test_correct_practice_awards_xp_and_advances_stage` expectation (0→1 immediately).

**Overall "Perfect" status, wired end-to-end.** `perfect_at` existed on
`UserItemProgress` since Slice 1b but nothing ever set it. `is_perfect_across()` checks
every *shipped* category (`PERFECT_CATEGORIES = (sentences, listening)` — `speaking` is
excluded until it has a practice mode, else Perfect would be unreachable for the whole
MVP) against Cinco, plus the item's SRS stage being Fluent. Checked in `grade_practice`
right after a stage advances. `PracticeGradeOut.perfect_overall` fires exactly once, the
moment it's newly achieved, distinct from the existing per-category `perfect` flag
(true on every correct answer once that one category is maxed).

**New: `services/items.py` + `GET /me/items` + `GET /me/items/{type}/{id}/progress`.**
The route PLANNING §3 always listed but never built. Per-item view assembles SRS state
(stage, next review, leech state/score, accuracy computed from all-time `ReviewAnswer.
original_correct` — not `total_incorrect`, which counts wrong *attempts* and can exceed
the review count), the three practice-stage rows (with `live: false` on `speaking` so
the UI can gray it out honestly), and up to 25 recent answers newest-first. History
includes lesson-quiz answers too, since `grade_quiz_answer` already writes to the same
`ReviewAnswer` table — a word's "full history" starts at its quiz, not its first review.
`/me/items` returns every started item, leeches-then-weakest-stage first, for the list
page. 404s (not silently empty) for items the user hasn't started yet.

**Frontend:** `/items` — a sortable-by-need list, leech/perfect badges, Uno..Cinco pip
row per item. `/items/[type]/[id]` — SRS card (stage, next review, accuracy, leech),
practice-stage card (progress bar per category, "coming soon" for speaking, "next stage
available in Xh" while gated), and a history feed (direction, correct/incorrect, undo
tag, stage transition). Linked from the header nav, the dashboard's "tricky items" tile,
and a new banner in the practice runner when `perfect_overall` fires.

**Tests: 192 backend** (+4: gate/perfect-across domain cases; +3 DB: listening-advances-
listening-not-sentences regression, gate holds-then-clears, perfect_at needs both
categories + Fluent; +6 for the new `/me/items*` routes) + 3 frontend. No migration —
`user_item_practice_stages` and `perfect_at` already existed in the schema, just unused.
Zero drift.

**Note for Jacob:** running this locally in Claude Code (vs. the browser session that
did slices 1–7) needed a one-time environment fix — `apps/api` had no venv with deps
installed, and `apps/web/node_modules` was missing `jest-environment-jsdom` despite it
being in `package.json`. Created `apps/api/.venv` (gitignored, not committed) and ran
`npm install` in `apps/web` to sync `node_modules` with the existing lockfile — no
dependency versions changed. Also: `mypy app` in `apps/api` currently reports ~90
pre-existing `strict = true` violations (mostly `dict`/`list` missing type args and
route handlers missing return-type annotations) spread across files from every earlier
slice, not introduced here — worth a cleanup slice if strict mypy is meant to gate CI.
Separately, there's a stray tracked `slice-6/` directory at the repo root (committed in
f995ca0) that looks like a leftover zip-extraction folder from the browser workflow —
flagging in case you want it removed.

**Next — slice 9:** guided tour + drag-to-customize dashboard, or slice 11 (email +
password reset) if account lockout risk outweighs the polish work.

---
## Slice 9 — Guided tour + dashboard customization (2026-07-23)

**The dashboard is now the learner's, not ours.** `domain/widgets.py` (pure) owns the
catalog and the layout rules; `services/dashboard.py` only reads and writes. A layout is
an ordered list of visible widgets — order is list order, a removed widget is simply
absent — which turns add, remove, and move into ordinary list operations and keeps the
stored JSON small enough to read at a glance.

Every layout passes through `normalize` on the way in *and* on the way out, and the rules
there are all about never letting a dashboard break:

- unknown keys are dropped rather than stored, so a stale client naming a widget we
  deleted can't wedge someone's dashboard
- duplicates collapse to the first occurrence
- spans clamp to what each widget can actually render at (XP maxes at 2 columns; the
  welcome banner needs at least 3)
- unreadable input degrades to the defaults rather than raising — opening your dashboard
  to a stack trace is a far worse outcome than a layout reset
- an empty layout is legal, because removing everything is a choice

The `PUT` returns what was *stored*, not what was sent, so the client's next render always
matches the database.

**Reordering works two ways, and the keyboard path is the primary one.** Every card in
edit mode has real ← → buttons; dragging is the shortcut layered on top, not the other way
round. Each move is announced in a live region, since a card silently changing position is
invisible to anyone not watching the screen. Saves are optimistic and immediate; a failed
save reverts the grid to what the server last confirmed rather than leaving the two out of
step. Client-side move/reorder helpers mirror the Python rules exactly and are tested on
both sides — if they drift, a dragged card visibly jumps back after the save lands.

**Three new cards** so the customizer has something to offer: next review, SRS stages
(all nine, with counts), and lessons ready. All three read fields `/me/stats` already
returns — no new backend data.

**Guided tour** (`components/tour.tsx`): speech bubbles that point at real elements, found
by `data-tour` attributes rather than rendered as fake screenshots, so the tour cannot
drift out of sync with the UI it describes. A missing anchor still shows its step, centred,
instead of pointing at nothing. It is a labelled modal dialog that takes focus on every
step and traps Tab; Escape skips, ← / → move, Enter advances; progress is text ("STEP 2 OF
5") and not only dots; transitions are transform/opacity and stop under
`prefers-reduced-motion`. `step_index` persists as the learner advances, so a refresh
mid-tour resumes rather than restarting.

A finished tour never restarts on its own. There is an explicit "replay the tour" link,
which is a deliberate departure from §14's "not replayable" — that rule was written about
the five-slide onboarding, and "I clicked through that too fast" deserves an answer
(**R-21**, say the word and it goes).

**Removed the redundant items nav link.** An item is always reached from the level it
belongs to, so a top-level entry point was a second door into the same room.

**Migration `c3f81a7d2b64`** adds `user_tour_state` (user, tour key, step index,
completed_at, skipped). A table rather than a flag on `user_settings` because tours are
plural and will keep arriving — a boolean column per tour means a migration every time.

`db/seed.py` now mirrors `domain/widgets.CATALOG` into `dashboard_widgets` instead of
carrying its own list. The code catalog has to be the source of truth: a widget only
exists if there is a component that can render it, which is a fact about the code.

**Tests: 231 → 272 backend** (+41: 27 layout-rule unit tests covering normalization,
clamping, hostile input, and clamped-not-wrapping movement; 14 integration tests covering
per-user scoping, the stored-vs-sent response, empty layouts, reset, tour resumption, and
the rule that a stale tab can't drag the tour backwards) + 30 → 55 frontend (+25: 14
tour behaviours including Escape-always-works and no-auto-replay, 11 layout helpers).

**Next:** slice 10 — intermissions, immersion mode, changelog (closes Phase 4).

### Open questions from this slice

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-21 | §14 says onboarding is not replayable; the dashboard tour has a replay link. | ⚙ Replay stays for the tour, not for the five-slide onboarding. |
| R-22 | `dashboard_widgets` is now descriptive, not authoritative — the code catalog is. | ⚙ Table kept for readability; drop it in a later slice if it stays unread. |
| R-23 | Widget spans are per-widget clamped but not user-adjustable in the UI yet. | ⚙ The API accepts spans; the resize control is a small follow-up. |
| R-24 | Old widget keys (`journey`, `heat_map`, `streak`, …) are seeded but have no components. | ⚙ Left in the table; they enter the catalog as their widgets get built. |

---
## Slice 10 — Intermissions, immersion mode, changelog (closes Phase 4) (2026-07-23)

**Intermissions** (§17) are short readings that appear between lessons — a culture note, a
pronunciation tip, a regional quirk. There is nothing to answer; viewing one is the whole
interaction, so the popup is deliberately easy to leave (Escape, the button, or the
backdrop) and marks itself viewed on dismissal.

`domain/intermissions.py` (pure) decides when one fires. Four trigger kinds — `level_start`,
`lesson_complete`, `items_learned`, `srs_stage` — with the level/lesson optional so a
trigger can wildcard. The module is total: an unrecognised or malformed trigger never
matches rather than raising, because a bad row written by an admin should mean "this one
doesn't show", not "lessons are broken". A test covers `None`, `42`, `[]`, `{}`, and
`{"kind": "nonsense"}` all resolving to False.

Two things the client does not get to decide. The event and level come from the browser —
it knows what the learner just did — but the *thresholds* are evaluated from the database,
so a crafted request can't unlock every intermission at once. And `intermissions_enabled`
is honoured server-side; the setting would be decorative if the UI were the only thing
checking it.

At most two fire at once. Two short readings between lessons is a pause; six is a wall,
and a learner will start dismissing them unread.

**Ten hand-written intermissions** ship in `db/seed_intermissions.py` — gendered nouns, the
five steady vowels, ustedes vs vosotros, why wrong answers are the point, ser/estar beyond
"permanent vs temporary", tú/usted, the two r sounds, why intervals stretch, diminutives,
and inverted question marks. All original prose. Nothing borrowed: this is a paid product,
and lifted explanations are both a licensing problem and a quality one (§6).

**Immersion mode** (§16) turns the app's own chrome Spanish at level 10. The scope is
deliberately narrow and stated in the code: navigation, buttons, and widget labels
translate; item meanings, lesson instructions, user-written content, and error messages do
not. An explanation you cannot read is not immersion, it is a locked door.

The unlock is enforced server-side (`PUT /me/immersion` returns 403 when locked — hiding
the toggle would not be enough), and turning immersion *off* never requires the unlock: if
the rule ever changed, someone already in immersion must be able to get back out. A test
pins that asymmetry. A dictionary-parity test fails if the Spanish strings ever fall behind
the English ones, or if a Spanish string is left accidentally identical.

**Changelog** (§21). Public list — what shipped is not a secret — with per-user unread
counts derived from `user_changelog_reads.last_read_at`, and an unread badge in the footer.
Admin CRUD is capability-gated (`content_edit` to write, `content_publish` to publish,
`content_archive` to delete) and every mutation writes an audit row in the same
transaction. Deletes are soft. `published_at` is stamped once, on first publish: editing
and re-publishing an entry should not shove it back to the top of everyone's unread count.

**Requested changes.** The customize controls moved to the *bottom* of the dashboard —
customizing is occasional, reading your dashboard is what you came for, and the controls
were pushing content down every visit. The add-a-card menu now opens upward to match. And
there is a **footer** (§21) with Product and Resources columns. Destinations that don't
exist yet render as plain text with a quiet SOON marker rather than linking to a 404 — an
honest gap beats a dead link, and each page just flips a flag when it ships.

**Security note worth recording:** intermission and changelog bodies support `**bold**`,
rendered by splitting text into React nodes rather than setting `innerHTML`. Admin-authored
is not the same as safe — "trusted author" is exactly the assumption that turns one
compromised editor account into stored XSS. A test asserts that `<img src=x onerror=...>`
in a body renders as literal text and produces no element.

**No migration.** `intermissions`, `user_intermission_views`, `changelog_entries`,
`user_changelog_reads`, `user_settings.intermissions_enabled`, `user_settings.immersion_mode`,
and `profiles.immersion_unlocked_at` were all in the schema from slice 1b.

**Tests: 272 → 325 backend** (+53: 30 trigger/immersion unit tests, 23 integration covering
draft invisibility, the server-side settings check, per-user history, unread arithmetic,
soft delete, capability gating, and the locked-immersion 403) + 55 → 80 frontend (+25:
i18n parity and fallbacks, popup dismissal paths, the XSS assertion, footer states).

**Phase 4 is now closed.** Next: slice 11 — email + password reset.

### Open questions from this slice

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-25 | Your slice-10 note described "vacation/pause mode that freezes SRS scheduling". That is a different feature from §17 intermissions — I built §17. | ⚙ Vacation mode is unbuilt. It touches review scheduling, so it wants its own slice rather than being bolted on. Say the word and it goes in next. |
| R-26 | The footer only appears on pages this slice touched (dashboard, changelog, intermissions). | ⚙ Add `<Footer />` to `app/layout.tsx` for site-wide, or per page as they're revisited. |
| R-27 | Features / How it works / Pricing / Support / FAQ / Community are footer stubs. | ⚙ Marked SOON. Pricing and support arrive with slices 12–13. |
| R-28 | Immersion translates ~45 UI strings; the rest of the app is still English under immersion. | ⚙ The dictionary grows as pages get revisited; parity is test-enforced so it can't silently rot. |

---
## Slice 11 — Email + password reset, decks, card-grid levels (2026-07-24)

**Password reset actually works now**, end to end. The placeholder page is replaced by a
real two-mode flow: request a link, then set a new password from the emailed token.

The security shape is the point of this slice. `domain/email_tokens.py` (pure) generates a
256-bit URL-safe token, stores only its SHA-256 hash, compares in constant time, and
enforces single use and a short life (reset one hour, verification a day). A database leak
yields hashes, which can't be redeemed — the same reasoning as refresh tokens.

`services/account.py` enforces **no account enumeration**: `forgot-password` returns the
identical response whether or not the address has an account, sends no email in the unknown
case, and the frontend swallows any error so nothing distinguishes the two. Redemption is
server-authoritative, single-use, and consumes the token in the same transaction that
changes the password. A successful reset **revokes every existing session** — resetting is
what you do when you fear compromise, so old sessions must not survive it. Requesting a new
link invalidates the old one. Tests cover all of it, including the expiry boundary and the
session-revocation.

**Email verification** ships alongside: a link fires on signup (wrapped so a mail outage
never turns a successful signup into a 500), confirmable at `/verify-email`, re-sendable
from the API, idempotent on replay.

**Email is behind a provider interface** (`app/email/`), the same pattern as the
audio/speech abstractions. SMTP for Mailpit locally and a real relay in production;
Console (the default when no host is set, so a bare checkout runs the whole flow); Memory
for tests. Nothing here logs a message body or a token — an email body carries a one-time
credential, and logging it would undo the hashing (§25). The compose patch points the api
at Mailpit, viewable at http://localhost:8025.

**Requested UI changes:**

*Levels is now a grid of clickable cards.* Tapping a card expands it in place — no
navigation — to show every vocabulary and grammar item in that level as chips, each linking
to its detail page, with shortcuts to lessons and the full progress view. It reuses the
level-progress endpoint from slice 8, so there's no new backend for the expansion. Locked
levels stay locked and show their unlock progress.

*The header's "reviews" link is now "decks".* Reviews still exist at `/reviews` — they just
aren't the top-level nav item any more. Decks is a browsable, read-only reference: three
decks for vocabulary, grammar, and the intermissions you've seen. It's scoped to unlocked
content and never carries the private answer key — a test asserts the rejected-answer text
appears nowhere in the deck response. Nouns show their article, verbs don't (§6).

**Migration `a1d94c6e77b2`** adds `password_reset_tokens` and `email_verification_tokens`,
both hash-only with a unique index on the hash and a `consumed_at` for single use.

**Tests: 325 → 366 backend** (+41: 20 token/provider unit tests incl. the expiry boundary
and constant-time match; 21 integration covering no-enumeration, single-use, expiry,
link-supersession, session revocation, verification idempotency, deck level-scoping, and the
answer-key privacy assertion) + 80 → 92 frontend (+12: account client request shapes, deck
pagination).

**Next:** slice 12 — Stripe + subscription gates.

### Open questions from this slice

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-29 | Verification is sent and confirmable but nothing is *gated* on it yet. | ⚙ Deliberately soft — verification gates arrive with subscriptions in slice 12, where "verified email required to subscribe" has a natural home. |
| R-30 | Reset/verify are rate-limited at the edge (Cloudflare/Upstash §25), not in the handler. | ⚙ Consistent with the rest of /auth. The in-handler fallback limiter can come with the Redis work. |
| R-31 | The decks intermission cards reopen the reading popup but don't re-mark viewed (already viewed). | ⚙ Correct as-is; they're already in your history by definition. |
| R-32 | Production email needs a real provider + `EMAIL_BACKEND=smtp` and SMTP creds in env. | ⚙ Mailpit covers local/beta. Wire Resend/Postmark/SES when you pick one. |

---
## Slice 12 — Stripe subscriptions, the paywall, and an admin dev sandbox (2026-07-25)

**Phase 5 opens with monetization.** `domain/entitlements.py` (pure) is the single place
that decides what a learner may reach: it turns a subscription status plus the clock into an
Entitlement, and every gate — server-side and in the UI — reads from it. The gate itself is
one rule: **level 1 is free for everyone; a few practice types are free but capped to
level-1 content; everything else needs full access.**

The status machine covers free / beta / lifetime / paid_active / paid_past_due /
paid_canceled. Two behaviours are worth calling out because they're easy to get wrong:

- **past_due keeps access.** A failed payment moves the sub to past_due but access stays on,
  because that's exactly the dunning grace window — giving up the instant a card declines
  would punish the honest majority whose card expired (§19 failed-payment).
- **canceled lapses without a cron.** A canceled sub keeps access until its period end, and
  the entitlement recomputes that from the clock every request. There's no scheduled job to
  "downgrade lapsed users" — a lapsed cancel simply resolves to free the next time it's
  read. One less moving part to break.

**Stripe is behind a provider interface** (same pattern as email/audio). Real Stripe when
`STRIPE_SECRET_KEY` is set; a deterministic **fake** otherwise, which drives the entire
subscribe → webhook → entitlement lifecycle locally with no Stripe account and no network.
The webhook handler is written to be **idempotent** — Stripe retries, so every branch is a
set-to-value, never an increment, and a replayed event lands on the same state (there's a
test for exactly that).

**The R-29 verification gate lands here**, as promised in slice 11: starting checkout
requires a verified email (403 `email_unverified` otherwise). Confirming you own an address
before paying through it is the natural home for that gate.

**Admin grants** (`PATCH /admin/users/{id}/subscription`, gated on `subscription_manage`)
let an owner/admin hand out beta or lifetime access directly — the "selected users get free
lifetime subs" path from §19, which isn't a payment flow.

### The admin dev sandbox (your request)

A troubleshooting surface at `/dev`, gated on a new `dev_panel` capability held only by
owner and admin. It exists so you can exercise the real review and practice engines without
living through real SRS intervals or grinding a curriculum up from zero. Everything it does
is scoped to the caller's own rows.

- **SRS time scale** (`domain/dev_mode.py`, pure) — a multiplier on every interval. The
  "fast" preset turns one week into exactly 30 seconds (30 / 10080 minutes); "instant" makes
  everything due almost immediately. Crucially this is **not a second scheduling path**: the
  multiplier is applied at `next_review_at`, the single point that turns a stage into a
  schedule, so the sandbox tests the same engine a learner uses, only faster. Scale 1.0 (the
  default, and the only value a non-admin can ever hold) is a complete no-op. It's clamped to
  never exceed 1.0 or reach 0 — dev mode only ever speeds time up, and never makes an item
  due before it was reviewed.
- **Unlock all items** — marks every published item learned, so every practice type (which
  draws only from learned items) immediately has material. This is the answer to "test the
  grammar practice without doing all the reviews first."
- **Make all reviews due now** — pulls every scheduled review back to now.
- **Set stage** — forces one item to a specific SRS stage, to test a transition directly.

The `TESTING.md` document in the slice package is a full terminal + sandbox guide: running
the suites, seeding data, the curl equivalents of every sandbox action, simulating the
Stripe webhook lifecycle locally, reading Mailpit, and inspecting the database.

### Smaller requested change

The **footer now has a faded-white background** (`bg-white/70` + a light backdrop blur)
instead of being fully transparent — it reads as a distinct band while still letting a hint
of the page tint through. Pricing graduated from a SOON stub to a real link.

**Migration `b7e2f4a91c30`** adds `subscriptions` and two columns on `user_settings`
(`dev_mode`, `dev_srs_scale`).

**Tests: 366 → ~410 backend** (+~44: entitlement resolution incl. the past-due grace window
and the cron-free cancel lapse; dev-mode scaling incl. the 30-second-week assertion and the
clamp; the full webhook lifecycle incl. idempotency; checkout's verification gate; dev-panel
capability gating) + 92 → ~100 frontend (+~8: billing + dev client request shapes).

**Next:** slice 13 — forums + community, then slice 14 closes Phase 5 with support/feedback.

### Open questions from this slice

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-33 | Practice/level routes expose the entitlement but I did not retro-gate every existing route this slice — the paywall notice + entitlement are in place, wiring each route is mechanical. | ⚙ Gate is centralized in `entitlement_for`; apply it route-by-route as each is revisited, or in one pass next slice. During beta everything is free anyway. |
| R-34 | Real Stripe needs `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, price IDs, and the `stripe` pip package. | ⚙ Fake provider covers local/beta fully. Wire real Stripe when you leave beta. |
| R-35 | Dev-mode time scale affects only future scheduling; items already scheduled at real intervals keep them until reviewed (or "make reviews due now"). | ⚙ Correct and intended — that's why the "make reviews due" button exists. |
| R-36 | The `/dev` link in the header only appears for admins; the page itself also 403-guards, so it's safe if the link is ever shown wrongly. | ⚙ Defense in depth: link gated AND page gated. |

---
## Slice 13 — Community forums (2026-07-26)

Forums, built the way §18 asked: **browsable before they're writable**. Anyone signed in can
read every category, thread, and reply; posting sits behind a switch that's off by default,
so the community can exist and be seen while it's being readied.

**Safety before features.** `domain/forum.py` (pure) holds the three rules that make a forum
survivable, each a deterministic unit test:

- **Sanitization.** Every stored string has HTML tags stripped, control characters dropped,
  and runaway whitespace collapsed. User-generated content is the classic stored-XSS vector,
  so we strip rather than trust — and the frontend renders the result as plain text (never
  innerHTML), making this defense in depth rather than the only line. A test asserts
  `<script>alert(1)</script>hola` stores as `alert(1)hola`.
- **Rate limiting.** `can_post` answers "posted too much, too fast?" from a person's recent
  post times (threads + replies combined): at most 6 in a rolling 10 minutes. The edge
  limiter is the first wall; this is the second, per-user. A friendly `seconds_until_can_post`
  drives the "try again in ~N seconds" message.
- **Auto-hide on reports.** Three distinct people flagging a post hides it pending a
  moderator — the crowd isn't forced to keep looking at abuse while waiting for a human — but
  report count alone never *deletes* anything.

**The posting gate is three ordered checks** in the service: is posting enabled globally? is
this category open? is this person under the rate limit? Only then does anything get written,
and only after sanitization. All enforced server-side; a test confirms posting returns 403
`posting_disabled` when the switch is off, because a client-only gate would be decorative.

**Moderation** reuses the existing `forum_moderate` capability (moderator / admin / owner) —
no new authorization machinery. Moderators hide, unhide, and soft-delete; hidden and deleted
content stays in the row (with who and when) and is filtered from public reads but visible to
moderators, who also get a report queue. Every moderation action writes an audit row. A
`get_optional_user` dependency (new, in `auth/deps.py`) is what lets one public route show
hidden posts to a moderator and not to anyone else.

**Reads are genuinely public** (well, auth-required but not capability-gated): the category
grid, thread lists, and thread detail all work for any signed-in user. Reports are one-per-
person-per-target (a unique constraint), so the auto-hide threshold counts distinct people,
not clicks — re-reporting no-ops.

Five categories seeded per §18: Grammar Help, Vocabulary, Speaking Practice, Bug Reports,
Feature Requests. The footer's "community" link graduated from a SOON stub to a real
`/community` route.

**Migration `c4a1f9d2e8b7`** adds the four forum tables.

**Also folded in — the slice-12 hotfix follow-up.** `resolve_entitlement` now tolerates an
unknown/legacy subscription status (the pre-existing table defaults `status` to "active",
which isn't in the new enum) by treating it as free rather than raising. During beta
everything is free anyway; this just removes a latent crash path the hotfix exposed.

**Tests: ~410 → ~455 backend** (+~45: 18 domain unit tests for sanitization, the rate-limit
window arithmetic, auto-hide, and slugs; ~27 integration covering public reads, the posting
switch, sanitization end to end, the rate limiter tripping, report auto-hide, and the
moderator-only hide/restore/queue) + ~100 → ~110 frontend (+~10: forums client shapes).

**Next:** slice 14 — support + feedback inbox, which closes Phase 5.

### Open questions from this slice

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-37 | The posting switch is a config/env flag, not a DB-backed admin toggle. | ⚙ Simplest correct thing for "browsable, posting later." Promote to an admin UI toggle when you want to flip it without a restart. |
| R-38 | Rate limit is 6 posts / 10 min, in-handler. The edge limiter (Cloudflare/Upstash) is separate and still recommended for anonymous flood protection. | ⚙ Tune the numbers in `domain/forum.py`; they're constants with tests. |
| R-39 | Threads route by id, not slug. Slugs are stored for future SEO-friendly URLs. | ⚙ Add slug-based routing when SEO matters; ids are stable now. |
| R-40 | Reports currently hardcode "abuse" as the reason from the UI button; the API accepts spam/abuse/off_topic/other. | ⚙ Add a reason picker to the report button when you want finer signal. |

---
## Slice 14 — Support & feedback inbox (+ requested tweaks) (2026-07-27)

**Phase 5 closes here.** The support/feedback loop from §22 and §30, built on the
`feedback_tickets` table that's existed since the initial schema — so this slice adds the
service, routes, and UI, not the table (no repeat of the slice-12 collision).

**Every page gets a feedback button.** It captures the current route and the browser's
user-agent automatically, so a bug report arrives with the context to reproduce it — the user
just types what happened. It renders only when signed in (a ticket needs an author). The same
backend powers a fuller `/support` page and a static `/faq`/about page, retiring two footer
SOON stubs.

**The admin inbox** (`/admin/feedback`, gated on the existing `feedback_manage` capability —
moderator/admin/owner) lists tickets filterable by **unanswered / answered / pinned**, with
badge counts. Admins reply (which flips the ticket to "answered" and stores the response),
and pin. Content is sanitized on the way in (same strip-tags/collapse rules as forums), and
submission is rate-limited (5 per 30 min per user) on top of the edge limiter.

**Email to the owner.** On each new ticket, a best-effort notification goes to
`jacobmelen17@gmail.com` (override with `FEEDBACK_EMAIL`) through the slice-11 email provider —
locally that's Mailpit. It's deliberately best-effort: the ticket row is the durable record
and shows in the admin tab regardless, so a mail misconfiguration never fails a user's
submission. `email_sent_at` is stamped only on a real send.

**Migration `d5b2c8e1a9f4`** adds `admin_response` / `responded_at` / `responded_by` to
`feedback_tickets`, and backfills `profiles.onboarding_completed_at` for existing users (see
below).

### Requested tweak 1 — welcome card above lessons/reviews

The dashboard now shows the "welcome back" card **above** the two big lesson/review action
buttons, rather than below them in the widget grid. A one-line reorder in `dashboard/page.tsx`.

### Requested tweak 2 — reset progress to re-test onboarding

This needed a real fix, because onboarding completion was only remembered in `localStorage`
and sign-in always went straight to the dashboard — so onboarding could never re-show on
login. Now:

- The unused `profiles.onboarding_completed_at` column is the **source of truth**. `/me`
  reports `onboarding_completed`, and a new `POST /me/onboarding/complete` records it when the
  slides finish (the `/welcome` page now calls it). The migration **backfills existing users**
  to already-onboarded so this change doesn't resurface the intro for anyone unexpectedly.
- Sign-in routes to `/welcome` when `onboarding_completed` is false, else to the dashboard.
  New signups (NULL) see it; everyone else doesn't.
- The admin dev sandbox (`/dev`) gets a **"reset my progress"** button →
  `POST /api/v1/dev/reset-progress` (gated on `dev_panel`, scoped to the caller). It clears
  the caller's SRS progress, review/practice sessions and history, the XP ledger, and
  intermission views; zeroes the profile's XP/points/rank/current-streak; and nulls the
  onboarding stamp. It deliberately **keeps** journals, forum posts, feedback, subscription,
  settings, and widget layout — losing your writing to a progress reset would be a nasty
  surprise. So: reset → sign out → sign back in → onboarding plays, on a fresh account.

### Also fixed — a slice-13 bug

The forum thread page destructured `const { me } = useAuth()` but the context exposes `user`,
so `me` was always undefined and the **moderator hide/delete controls never rendered**.
Corrected to `user` here.

**Tests: ~455 → ~490 backend** (+~35: feedback domain sanitize/rate-limit/category; the full
submit→list→filter→respond→pin flow; the inbox capability gate; onboarding persistence via
`/me` and `/complete`; and the dev reset clearing the onboarding stamp) + ~110 → ~120
frontend (+~10: feedback + onboarding client shapes).

**Phase 5 is now complete.** Next: slice 15 — vacation/pause mode (R-25), the SRS-freeze
feature, which gets its own slice because it touches review scheduling.

### Open questions from this slice

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-41 | The feedback email uses the slice-11 provider via a defensive call that tolerates a couple of interface shapes. If your provider's `send`/`EmailMessage` differs, the ticket still saves but no mail goes out. | ⚙ Verify against your actual `app/services/email.py`; tighten `_notify_owner` to its exact signature. Locally Mailpit shows whether it sent. |
| R-42 | Reset keeps journals/forum posts/feedback by design; only "learning progress" is cleared. | ⚙ If you want a scorched-earth reset too, add a second button that also clears those. |
| R-43 | Sign-in→onboarding relies on the backfill having stamped existing users. If you seeded users outside migrations, run the one-line UPDATE from the migration. | ⚙ Backfill is idempotent; re-running the UPDATE is safe. |

---
## Slice 15 — Vacation / pause mode (R-25) (2026-07-28)

The SRS-freeze I split out of the original slice-10 note because it touches review
scheduling — the app's core invariant. The whole slice is organized around one promise:
**pausing and resuming must never corrupt an item's `next_review_at`.**

**The model.** While paused, nothing comes due — the schedule is frozen. On resume, every
item that existed *before* the break has its due date pushed forward by exactly the break's
length. So an item three days from due when you left is three days from due when you're back:
no overdue pileup, and nothing advanced for free. Items learned *during* the break are left on
their natural schedule — they were never frozen, so they aren't shifted. The discriminator is
`unlocked_at <= paused_at`.

**Why it's trustworthy.** All the arithmetic lives in `domain/vacation.py` as pure functions
(`compute_shift`, `should_shift_item`, `shifted`, `paused_days`) with deterministic unit tests
that assert the invariant directly — time-until-due preserved, overdue-stays-overdue,
during-break items untouched, resume-before-pause is a no-op, and a sanity cap (`MAX_SHIFT` =
10 years) so a bad clock can't fling the schedule into the next decade. The shift is applied in
Python, not SQL, so it behaves identically on Postgres and the test DB (no reliance on
database interval arithmetic).

**Data.** One new table, `vacation_periods` (migration `e6c3d9f2b1a5`, purely additive). A
period is *open* while `ended_at` is NULL — that's the single source of truth for "am I
paused." Resuming stamps `ended_at`, the shift applied, and how many items moved, so every
break is auditable. At most one open period per user, enforced in the service; pausing while
paused is a no-op that preserves the original start.

**Integration points (small and precise).**
- `reviews.due_items` — the one query that defines "what's due" — returns empty while paused.
  That freezes review sessions at the source.
- `/me/stats` — zeroes `reviews_due` while paused and returns a `vacation` block
  `{paused, since, days}`, so the dashboard shows a real paused state rather than a misleading
  "all caught up."
- API: `GET /me/vacation`, `POST /me/vacation/pause`, `POST /me/vacation/resume`.

**Frontend.** A vacation card on the dashboard with two faces — an invitation to pause before
a trip, and a calm "on a break since…" with a resume button that reports how many items were
rescheduled. The welcome line reads "reviews are paused — enjoy your break" while away. Full
loading/error handling; no state relies on colour alone.

**Decision — lessons stay open during a break.** Freezing reviews solves the pileup problem;
blocking lessons isn't needed for correctness because during-break items aren't shifted. So you
can still learn on vacation if you want, and it can't corrupt the schedule. (Flagged as R-44 in
case you'd rather freeze the whole loop.)

**Tests: ~490 → ~515 backend** (+~25: the pure shift invariants; pause opens one period;
double-pause no-op; state reports days; reviews frozen while paused; resume shifts pre-break
items by the break length; during-break items untouched; resume-when-not-paused no-op;
pause→resume→pause again) + ~120 → ~125 frontend (+~3: vacation client).

**Next: slice 16 — placement test (§31).**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-44 | Lessons are allowed during a break; only reviews freeze. | ⚙ If you'd prefer a true "everything paused," add a `vacation.is_paused` guard to the lesson-start endpoints — the shift stays correct either way. |
| R-45 | Streaks are not frozen during a break yet — a long vacation would still break a study streak. | ⚙ Streak-freeze during vacation is a natural follow-up; it lives in the streak computation, which this slice didn't touch. |
| R-46 | No max break length beyond the 10-year `MAX_SHIFT` safety cap. | ⚙ Add a product cap (e.g. auto-resume after 90 days) later if desired. |

---
## Slice 17 — Speech scoring + speaking practice (§7, §33) (2026-07-30)

The speaking loop, built the way the spec asks for twice: **browser-native recognition for the
MVP, behind a provider abstraction** so a third-party scorer can be swapped in later, and
**recordings processed transiently and never stored** — only a text transcript ever reaches the
server.

**The scoring engine is the tested core.** `domain/speech.py` scores a transcript against the
expected phrase and returns a 0–100 score plus a word-by-word breakdown. It's Spanish-aware
(accents, case, and punctuation are normalized away, because consumer speech-to-text routinely
drops accents) and token-level: the score is an F1-like overlap of the two word sequences via
their longest common subsequence, so both missing words and extra filler cost you — and the
per-word matched flags come from that same alignment, so what's highlighted always matches the
number shown. Deterministic, so it's unit-tested exactly like the SRS and placement cores
(exact match, accent-insensitivity, one-word-missing, filler penalty, accepted-variant
selection, configurable threshold, empty input).

**The provider seam is real.** `services/speech.py` defines a `SpeechScorer` protocol with two
implementations: `LocalScorer` (the MVP default — scores the transcript the browser already
produced, no external service, no audio) and `ExternalScorer` (a registered placeholder for a
future audio-in, phoneme-level service). `get_scorer()` selects by name, defaulting to the
`SPEECH_PROVIDER` env var. Selecting the external provider without an adapter raises a clear
error rather than silently degrading — the swap point is explicit and covered by tests.
Switching providers later is a config change plus one adapter, not a rewrite.

**Server-authoritative, and it reuses the practice machinery.** `services/speech_practice.py`
resolves the expected phrase server-side (the client can't declare what counts as right),
scores through the provider, and — on a pass — advances the *speaking* practice stage
(Uno..Cinco, via the existing `advance_practice_stage`) and awards XP. Scoring is idempotent by
key: a retry recomputes the (deterministic) score but never re-awards XP or double-advances the
stage. Practice only covers items the learner has actually met; scoring an unlearned item is a
403. Like all practice, it never touches the SRS schedule.

**No migration** — speaking rides on the existing `user_item_practice_stages` and XP tables.

**Frontend.** `/practice/speaking` runs the say-the-phrase loop. `useSpeechRecognition` wraps
the Web Speech API and is the client-side seam — a service-based recorder can replace the hook
without touching the page, which only consumes `{ supported, listening, transcript, … }`. When
recognition is unavailable or the mic is blocked, a typed fallback keeps the exercise usable.
The prompt has a text-to-speech replay, word feedback never relies on colour alone (a ✓/·
marker carries the meaning too), and animations respect reduced-motion.

**Privacy.** The request body is a text transcript and nothing else — no audio is uploaded or
stored, which the frontend test asserts (no `audio` field on the payload).

**Tests: ~545 → ~570 backend** (+~25: the pure scoring battery; the provider factory/seam
including the external-not-configured path; start returns learned items only; a correct
utterance passes, awards XP, and advances the speaking stage; the client can't fake a pass;
idempotent retry; unlearned-item 403) + ~130 → ~133 frontend (+~2: speaking client, transcript-
only payload).

**Next: slice 18 — reading resource + community journals (§7).**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-51 | Speaking prompts are single vocabulary terms for now, not full sentences. | ⚙ The engine already scores multi-word phrases; wire example sentences in when sentence-level speaking is wanted. |
| R-52 | The 24h between-stages cadence (§10) isn't enforced here — matching the existing practice service, which advances on each correct answer. | ⚙ A cross-cutting practice concern; add the gate to `advance_practice_stage`'s callers everywhere at once. |
| R-53 | Feature-unlock schedule (§7: practices unlock over levels) isn't gated yet — speaking is available once you've learned ≥1 word. | ⚙ Fold into the `/me/practice/availability` map when that schedule is finalized. |
| R-54 | Web Speech API support is uneven (Chrome/Edge good; Firefox/Safari limited). | ⚙ The typed fallback covers unsupported browsers today; the external-provider seam is the long-term answer. |

---
## Slice 18 — Community journals (§7) (2026-07-31)

The "share journals for feedback later" feature you flagged in §7. It extends two systems that
already exist — journals and the forums/moderation stack from slice 13 — rather than inventing
new machinery. (The reading resource, the other half of §7's writing-and-reading, is the next
slice; it's a content-authoring feature large enough to deserve its own.)

**The privacy invariant is the whole point, and it's a pure, exhaustively-tested function.**
Journals are private by default. `domain/community_journal.can_view_shared_entry` is the single
gate every community read passes through, and it's deliberately conservative — the default
answer is "no." A private entry is visible to its owner and *no one else, not even a
moderator*; a shared entry is visible to the community unless a moderator has hidden it, in
which case only moderators can still review it; and the owner always sees their own entry.
Requesting a private entry returns the same 404 as a nonexistent one, so sharing status never
leaks. Unit tests assert each branch directly, and the DB tests prove it end-to-end: another
user gets 404 on a private entry, can't share what isn't theirs, and can't comment on an
unshared entry.

**Sharing is a `visibility` transition — no new concept.** The `JournalEntry.visibility` column
(present since the first schema, commented "community sharing later") flips between "private"
and "community". Migration `a8f3c1e9d2b4` adds `shared_at` (feed ordering), `share_hidden` +
`share_hidden_reason` (moderator removal that leaves the owner's copy untouched), and the
`journal_feedback` table. Purely additive.

**Feedback reuses the forum patterns.** Comments are only accepted on entries that are currently
shared and visible; bodies are sanitized (markup stripped, rendered as plain text) and
rate-limited (8 per 10 minutes); a moderator (the existing `forum_moderate` capability) can hide
a comment or a whole shared entry without deleting anything. Hidden feedback disappears for
readers but stays visible to moderators for review.

**Low blast radius.** All the new endpoints live in a dedicated router that acts on entries by
id (verifying ownership), so the existing journal service is untouched. The frontend adds a
`/community/journals` hub (your entries with share/unshare toggles + the community feed) and a
`/community/journals/{id}` reader with the feedback thread; both carry their own Forums↔Journals
tabs, so navigation works regardless of other nav. The one edit to the existing community page —
a link to journals — is a *soft* patch: if its anchor isn't found the installer notes it and
stays green, because the journals pages are reachable on their own.

**Tests: ~570 → ~600 backend** (+~30: the visibility-invariant battery, sanitize/validate/
rate-limit; share → feed → read; unshare removes it; a private entry is 404 to others; can't
share another's entry; feedback only on shared entries and is sanitized; moderator hides a
comment and an entry; the owner still sees a mod-hidden entry) + ~133 → ~136 frontend (+~3:
community-journal client).

**Next: slice 18b/19 — the reading resource (§7): short stories and imported texts to annotate,
translate, and dissect.**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-55 | One global community feed — no per-community/per-language grouping yet. | ⚙ §7 says "join communities"; when communities are modeled, scope the feed and the share target to a community id. |
| R-56 | Feedback can be hidden by moderators but not yet *reported* by users. | ⚙ Mirror the forum report table (one report per person, auto-hide at N) when reporting on journals is wanted. |
| R-57 | Sharing doesn't award XP or points. | ⚙ Intentional for now (feedback is its own reward); revisit if you want to incentivize community help. |
| R-58 | Archived entries can't be shared (feed lists non-archived only). | ⚙ Reasonable default; allow sharing archived entries if you'd rather. |

---
## Slice 19 — Reading resource (§7) (2026-08-01)

The other half of §7's writing-and-reading: a library of short texts a learner can read,
**tap-to-translate**, and **annotate** (highlight a phrase, leave a note — the "dissect" part).
Original texts are authored on the site; external links point out to curated material.

**Two pieces are pure, tested functions.** `domain/reading.validate_annotation` enforces that a
highlight's character offsets are a real, non-empty span inside the text — because the server
slices the stored quote from *its own* copy of the body using those offsets, an out-of-range
span has to be rejected before it's trusted. `can_view_text` is the visibility gate: only
published, non-deleted texts are public; drafts, in-review, archived, and soft-deleted texts are
visible to content editors only. `normalize_word` backs the lookup.

**Tap-to-translate reuses the vocabulary table.** A tapped word is normalized (accents and
punctuation stripped) and matched against `vocabulary_items.normalized_term`; a hit returns the
translation and part of speech, a miss says "not in your vocabulary yet." No new data — reading
and the SRS curriculum share one source of truth for word meanings.

**Annotations are private and server-authoritative.** The reader tokenizes the body so the
rendered text content matches the server's body exactly; a selection's offsets therefore line up
with what the server validates, and the stored quote is sliced server-side (`extract_quote`),
never taken from the client. Each learner sees only their own notes; external links can't be
annotated.

**Admin authoring is gated and audited (§22).** Content editors create/update texts
(`content_edit`) and publish them (`content_publish`) via `/api/v1/admin/reading`; every mutation
writes an `admin_audit_log` row in the same transaction, following the existing curriculum-admin
pattern. Texts move draft → published → archived (archive soft-deletes).

**Data.** Migration `b9d4e2f1a3c5` (additive): `reading_texts` and `reading_annotations`. A
clearly-marked demo seed (`app/db/seed_reading.py`, original hand-written micro-texts) keeps the
library non-empty in local dev; run `python -m app.db.seed_reading`.

**Frontend.** `/reading` (library, published only) and `/reading/{id}` (the reader). Words are
focusable buttons (keyboard translate); highlighting opens a note composer; your notes list below
the text with delete. A soft header link to reading (the pages are reachable directly regardless).

**Tests: ~600 → ~625 backend** (+~25: the annotation-range and visibility batteries; library lists
published only; a draft is 404 to users but readable by editors; word lookup reuses vocabulary and
normalizes; the annotation lifecycle with server-side quote; out-of-range rejected; another user's
notes are invisible; external links aren't annotatable; admin create/publish is gated and audited)
+ ~136 → ~139 frontend (+~3: reading client).

**Next: slice 20 — a second language (Tagalog), the first real exercise of the multilingual-ready
schema.**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-59 | Reading isn't paywall-gated yet — any authenticated user can read any published text (§19 gates content beyond level 1). | ⚙ Wire the entitlement check (from the subscriptions slice) into `get_text`/`list_texts` by level when you want reading behind the paywall. |
| R-60 | Annotations aren't rendered as inline highlights in the text yet — they're listed below it. | ⚙ Inline highlighting (mark the spans in-place) is a nice polish; the offsets are already stored to support it. |
| R-61 | Tap-to-translate matches single words against `normalized_term`; multi-word phrases and inflected forms won't always hit. | ⚙ Add lemmatization / phrase lookup later; the miss message is honest in the meantime. |
| R-62 | Select-to-annotate is pointer-based (keyboard users can translate words but not highlight spans). | ⚙ Add a keyboard range-selection affordance for full parity later. |

---
## Slice 20 — Second language (Tagalog) + language selection (§1, §32) (2026-08-01)

The first real exercise of the multilingual-ready schema. Every piece of content has always
carried a `language_id`; what was missing was a runtime notion of *which* language a learner is
studying — the services quietly hardcoded "es-MX". This slice introduces the active language,
threads it into the curriculum, and adds the two selection surfaces you asked for.

**Active language is a single source of truth.** `services/languages.py` owns it:
`get_active(user_id)` resolves the learner's `profile.active_language_code` to a `Language`,
falling back defensively (preference → es-MX → any enabled language → None only on a fresh,
unseeded DB) so a request never dies over an unset or since-disabled preference; `set_active`
only accepts an *enabled* language. `list_enabled` powers the pickers. Migration `c1a5f8e3b7d2`
(additive) adds `languages.enabled` (default true) and `profiles.active_language_code` (default
"es-MX"), so nothing changes for existing users.

**Threaded into the learning surface.** `learn.py` had two spots that resolved "es-MX" inline —
`list_levels` and `_module_or_404`. Both now go through a local `_active_language` helper, and
`_module_or_404` takes the user through its five callers, so viewing levels, opening lessons,
quizzes, and completing lessons all follow the chosen language. The proof is a test: with a
Spanish level and a Tagalog level both published, `/levels` returns the Spanish one by default
and the Tagalog one after `PUT /me/language {tl-PH}` — and never the other. (`_all_level_states`
already took a `lang_id`, and `_require_unlocked` derives it from the module, so unlock logic came
along for free.)

**The two selection surfaces.** A new `/choose-language` page is shown right after signup, before
the onboarding slides (the auth-form's post-signup redirect now points there). A header
`LanguageSwitcher` (🌐) lets a learner flip languages anytime; switching reloads so every content
surface refetches under the new language.

**Tagalog is real.** `app/db/seed_tagalog.py` registers Tagalog (`tl-PH`, stage names
Isa..Lima) and adds a small, clearly-marked **demo** Level 1 so selecting it shows content
immediately. This is demo data, not production curriculum — production Tagalog is expected via an
admin CSV import, exactly like Spanish (see R-63). Run `python -m app.db.seed_tagalog`.

**Tests: ~625 → ~650 backend** (+~25: `get_active` default + fallback when the active language is
disabled + None on an unseeded DB; `set_active` accepts enabled / rejects unknown; the API lists,
reads, switches, and rejects; auth required; and the threading proof that `/levels` reflects the
active language and changes when it's switched) + ~139 → ~142 frontend (+~3: languages client).

**Next: slice 21 — production hardening (Sentry, Plausible, health checks, backups, Cloudflare
WAF/rate-limit fallback).**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-63 | The admin CSV importer still targets es-MX (`_spanish(db)`), so a Tagalog curriculum can't be imported through the UI yet. | ⚙ Generalize the importer to take a target language (a `?language=` selector on the import endpoints) — the natural next step so real Tagalog content can be uploaded. |
| R-64 | Reviews are keyed by the learner's progress rows, so they span all languages studied rather than scoping to the active one. | ⚙ Scope the review queue to the active language (join item → language) when per-language review is wanted. |
| R-65 | `stats.lessons_available` and the placement flow still resolve es-MX internally. | ⚙ Route them through `_active_language` / `get_active` in a follow-up pass; low-risk, same helper. |
| R-66 | Reading already accepts `?language=`, but the reading pages don't yet pass the active language. | ⚙ Thread the active code into the reading client calls so the library follows the switcher too. |
| R-67 | A learner mid-onboarding who logs back in isn't re-sent to `/choose-language` (defaults to es-MX, changeable in the header). | ⚙ Gate `/welcome` on "language chosen" if you want the picker guaranteed before slides on every first run. |

---
## Slice 21 — Production hardening (§25, §26, §27) (2026-08-01)

The infrastructure a real service needs before it takes traffic: rate limiting, request-scoped
logging, security headers, health probes, optional error tracking, privacy-first analytics, and a
backup/restore runbook. Most of it is code + config (no migration), and it's all installed with a
single `install_observability(app)` call from `create_app`, so the blast radius is one line.

**Rate limiting is the tested core.** `domain/ratelimit.evaluate` is a pure sliding-window log:
given a client's recent hit timestamps and now, it decides allow/deny, prunes anything older than
the window, and computes retry-after — no state, no I/O, fully unit-tested (first hit, under
limit, at limit with retry-after, pruning, strict window boundary, zero-limit, unordered input).
`observability/ratelimit.py` stores those timestamps behind a provider seam: `InMemoryLimiter`
(default, single-node beta) and a `RedisLimiter` (Upstash, guarded import so the app runs without
the redis package), selected by `RATE_LIMIT_BACKEND`. `RateLimitMiddleware` applies a coarse
per-IP limit across the whole API — enough to blunt abuse of auth, review submission, and form
posts (§25) without touching every router — with health checks exempt so probes are never
throttled. Verified live against a real FastAPI app: 429 with Retry-After after the cap, per-IP
isolation, health exemption.

**Request-id + structured logging (§27).** Every request gets a stable id (honouring an inbound
`X-Request-ID` from Cloudflare/LB, else generated), echoed on the response and included in one
structured log line per request with method/path/status/duration — and *only* that, never bodies
or tokens (§25). **Security headers (§25):** nosniff, DENY framing, referrer + permissions
policy, a conservative CSP, and HSTS only when the request came over HTTPS (so local HTTP dev
isn't pinned). **Health probes (§27):** `/health/live` (process up) and `/health/ready` (pings
the DB, returns 503 when the DB is unreachable) for orchestrators and load balancers.

**Optional add-ons, off by default.** `init_sentry()` initialises Sentry only when `SENTRY_DSN`
is set *and* `sentry_sdk` is importable — both guarded, so error tracking is never a startup
dependency, and it never ships user PII. On the frontend, `<PlausibleScript />` loads cookieless
analytics only when `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` is set, and `track()` is a safe no-op
otherwise (tested: no-op without the script, forwards events with it, swallows a broken script).

**Reliability (§26).** `docs/RUNBOOK-backups.md` documents the two independent backup tracks —
Postgres (Supabase automated backups → PITR for paid prod, plus a pre-migration `pg_dump`) and
object storage (a scheduled bucket mirror, since DB backups don't cover Storage) — with a
restore procedure and a quarterly restore-drill checklist. `.env.slice21.example` lists every new
(all-optional) variable.

**No migration.** Nothing touches the schema.

**Tests: ~650 → ~665 backend** (+~15: the pure rate-limit battery; and the live middleware stack —
request-id generation + inbound echo, the security-header set, HSTS-only-over-https, 429 after the
cap with Retry-After, health exemption, per-IP isolation, default limiter is in-memory) + ~142 →
~145 frontend (+~3: analytics no-op / forward / error-swallow).

**Next: slice 22 — Stripe payments + subscription gates (Phase 5 monetization).**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-68 | Rate limiting is a single coarse per-IP middleware, not yet per-route tiers (tighter caps on login/review/support). | ⚙ Reuse `get_limiter()` as a per-route dependency where the spec wants a tighter cap; the seam is ready. |
| R-69 | The in-memory limiter is per-process — several API workers each keep their own counters. | ⚙ Switch `RATE_LIMIT_BACKEND=redis` (Upstash) once you run more than one worker; the `RedisLimiter` is in place. |
| R-70 | Edge protection (Cloudflare WAF + rate rules) is documented but configured in the Cloudflare dashboard, not in code. | ⚙ Add the app limiter as defence-in-depth behind Cloudflare; keep the WAF rules in the CF config. |
| R-71 | Analytics events (`track(...)`) aren't yet fired at the call sites (signup, lesson/review complete, demo clicks). | ⚙ Drop `track(AnalyticsEvent.X)` into those handlers in a small follow-up; the helper and event names are ready. |

---
## Slice 22 — Stripe billing + paywall (§19) (2026-08-01)

Monetization, built so the money logic is testable without ever touching Stripe. The
`Subscription` table already existed (tier / status / stripe_customer_id / period_end /
canceled_at), so this slice adds no schema — it adds the entitlement rule, the provider seam,
the billing service, and the paywall gate.

**The entitlement rule is the tested core.** `domain/entitlements.is_entitled` is a pure function
of role + tier + status: staff and beta testers always have access (the beta perk, §19), lifetime
has access until revoked, and a paid plan has access while active/trialing. `can_access_level`
encodes the boundary — level 1 is free for everyone, beyond needs an entitlement. No I/O, no
Stripe, exhaustively unit-tested (every role, every status, the lifetime and past-due edges, the
level boundary).

**Stripe sits behind a provider seam.** `services/payments.py` defines `PaymentProvider` with a
`FakeProvider` (the MVP default — checkout returns a local stub URL, webhooks are accepted as
plain JSON) and a `StripeProvider` (real adapter, guarded import so the app runs without the
`stripe` package). `PAYMENT_PROVIDER` selects; the whole subscribe → webhook → entitlement flow
runs and is tested with no Stripe account. Both providers emit one normalized event shape to the
service.

**Subscription state changes only from a verified webhook (or an admin grant), never a client
claim.** `services/billing.handle_webhook` is the state machine: created/updated → active on the
right tier, `invoice.payment_failed` → past_due (gated), `subscription.deleted` → canceled. A
learner with no `Subscription` row is treated as the beta default (free_beta/active), so nobody
who predates billing is locked out. The live service run walks the full lifecycle: beta default →
free-tier 402 at level 2 → fake checkout → webhook active → past_due → canceled → admin lifetime
grant (audited).

**The paywall is one gate.** `require_entitlement_for_level` is inserted at the top of the
curriculum's `_require_unlocked`, so every lesson route beyond level 1 returns a 402 `paywall` for
non-entitled users, before any SRS-unlock logic. Level 1 and the basic practice on level-1 content
stay free (§19). Reading/other-practice gating reuse the same helper (R-72).

**Frontend.** `/pricing` shows the free tier alongside monthly ($7) and annual ($60), with a
"you're all set" state for beta/lifetime/active members; a `PaywallNotice` component turns a 402
into a link to pricing rather than a dead end.

**No migration.** Reuses the existing `subscriptions` table.

**Tests: ~665 → ~680 backend** (+~15: the entitlement battery; entitlements require auth; beta
default entitled, free tier gated; plans listed; fake checkout URL; the full webhook lifecycle
active→past_due→canceled; admin grant-lifetime gated + audited) + ~145 → ~148 frontend (+~3:
billing client + price formatting).

**Next: slice 23 — the testing maps (CEFR / app / life), §7.**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-72 | The paywall gates lessons beyond level 1; reading and standalone practice aren't gated by level yet. | ⚙ Call `require_entitlement_for_level` (or `can_access_level`) in `reading.get_text` and the practice services to gate their level->1 content the same way. |
| R-73 | `free_max_level` is 1 and hardcoded; there's no per-level or per-feature pricing. | ⚙ Make the free boundary configurable (or a column on `languages`/`modules`) if you want a different free allowance. |
| R-74 | Past-due has no grace period — access is cut immediately on `invoice.payment_failed`. | ⚙ Add a grace window (keep entitled until `current_period_end`) if you'd rather soften failed payments. |
| R-75 | Stripe price ids, webhook secret, and the customer-portal config live in env/Stripe dashboard, not in code. | ⚙ Set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_MONTHLY/ANNUAL`, `STRIPE_WEBHOOK_SECRET` and `PAYMENT_PROVIDER=stripe` to go live. |

---
## Slice 23 — Testing maps (§7) (2026-08-02) — (slice-22 billing crash fixed upstream)

JLPT-style comprehension testing: audio + a caption, a question, four options, one right answer,
across three maps — **cefr** (standardized bands), **app** (only what the learner has covered),
and **life** (casual real-world scenarios). 20 XP per correct answer (§12).

**The rules are pure and tested.** `domain/testing.py` validates a submitted choice (rejecting
out-of-range indices and, importantly, `True` — bool is an int subclass), grades by equality
against the server-held answer, and scores a session. The critical property: **the correct index
is never serialized to the learner** — `_question_public` omits it, and grading compares
server-side. A live run confirmed the answer never leaks, a wrong pick scores zero, and the app
map only offers questions at or below the learner's reached level (and expands the moment they
reach the next one).

**Server-authoritative and idempotent.** `services/testing.start_attempt` selects published
questions for the learner's *active language* (slice 20), gated by `reached_level` for the app
map and by band/scenario for cefr/life, and stores an attempt. `answer` grades, records into the
attempt's JSON answer snapshot, and awards `xp_for(XpKind.test_correct)` — idempotent by key, so
a retry never double-scores. `complete` returns score / total / percentage. A foreign attempt
(someone else's) is a 404.

**Admin authoring, audited.** Content editors create questions (`content_edit`) and publish them
(`content_publish`) via `/api/v1/admin/tests/questions`; every mutation writes an
`admin_audit_log` row (§22). A clearly-marked demo seed (`app/db/seed_tests.py`) adds a few
original questions across all three maps so testing is demoable immediately.

**Data.** Migration `d2b6e4f9a1c8` (additive): `test_questions` (bank; `correct_index` private)
and `test_attempts` (one run, with a JSON answer snapshot so no second table is needed).

**Frontend.** `/tests` (hub) and `/tests/{map}` (runner: TTS on the caption, the question, four
keyboard-operable options with ✓/✗ feedback that never relies on colour alone, and a results
screen). A soft header link to testing.

**Tests: ~680 → ~700 backend** (+~20: the pure choice/grade/score battery; start doesn't leak the
answer; correct → 20 XP once (idempotent); wrong → 0; app-map level gating; complete scores;
foreign-attempt 404; admin authoring gated + audited) + ~148 → ~151 frontend (+~3: testing client).

**Next: slice 24 — generalize the admin CSV importer to any language + finish the multilingual
threading (R-63–R-67).**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-76 | cefr/life aren't paywall-gated; the app map is naturally limited by reached level (which for free users is level 1). | ⚙ Wrap cefr/life start in `require_entitlement_for_level` (or a flat entitlement check) if you want them behind the paywall. |
| R-77 | Question audio is referenced by `audio_asset_id` but the runner uses TTS on the caption for now. | ⚙ Resolve `audio_asset_id` to a stored clip (like lessons) once recorded audio exists; TTS is the honest fallback. |
| R-78 | The "life" map is scenario-tagged via `band` but has no scenario picker UI yet. | ⚙ Add a scenario chooser (Teuida-style) that passes `?band=` to start. |
| R-79 | Attempts aren't resumable across a refresh (a fresh start creates a new attempt). | ⚙ Add a "resume active attempt" lookup if mid-test recovery is wanted; the attempt row already persists the question order. |

---
## Slice 24 — Multilingual completion (§1, §32) (2026-08-02) — (slice-23 JSON-column crash fixed upstream)

The multilingual schema has been in place since slice 1 and selectable since slice 20; this slice
makes it *real end to end*: you can import a full curriculum for any language, and the review
queue follows whichever language you're studying.

**The CSV importer targets any language (R-63).** The two admin import endpoints hardcoded Spanish
via a `_spanish(db)` helper, even though the underlying `import_service` already took a
`language_id`. Now they accept `?language=<code>` (default `es-MX`, so existing calls are
unchanged), resolved by a generalized `_language(db, code)` that 422s on an unknown code.
`_spanish` stays as a thin delegate for any other caller. This is the first real exercise of the
schema's multilinguality: importing a Tagalog CSV under `tl-PH` creates items under Tagalog, keeps
them entirely separate from Spanish (the importer's idempotency key already includes
`language_id`), and nothing leaks across languages. Content still lands as draft for review — no
fabricated curriculum, exactly the "no imports until admin adds a CSV" intent.

**The review queue follows the active language (R-64).** `due_items` was keyed only by the
learner, so a learner who'd studied two languages saw both mixed together. It now scopes to the
active language's items (vocab + grammar), and — importantly — applies the limit *after* filtering,
so a backlog in one language can't crowd out the reviews that are actually due in the active one.
Switching languages in the header switches which reviews appear. A fresh, unseeded DB with no
enabled language falls back to unscoped rather than returning nothing.

**Both verified against a live database:** import under `tl-PH` creates Tagalog items with none in
Spanish; an unknown code 422s; the default is still es-MX; due items scope to the active language,
flip when it's switched, respect the limit after filtering, and include grammar.

**No migration.** Both changes are code-only (the schema already carried `language_id` everywhere).

**Tests: ~700 → ~712 backend** (+~12: import targets the requested language / defaults to Spanish /
rejects unknown / still capability-gated; due items scope to the active language / respect the
limit after filtering).

**Next: a polish pass for the remaining deferrals — paywall-gating reading & practice (R-72/R-76),
the 24h practice-stage cadence (R-52), the feature-unlock-by-level schedule (R-53), guided tours,
dashboard-widget customization, and threading the active language through stats/placement/reading
pages (R-65/R-66).**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-65 | `stats.lessons_available` and the placement flow still resolve es-MX internally. | ⚙ Route them through `get_active` like the learn surface; low-risk, same helper. |
| R-66 | The reading library/pages accept `?language=` but the frontend doesn't pass the active code yet. | ⚙ Thread the active language into the reading client calls so the library follows the switcher. |
| R-80 | The admin import UI doesn't expose a language selector yet — the API takes `?language=` but the panel still posts without it (defaults to es-MX). | ⚙ Add a language dropdown to the admin import form, sourced from `GET /api/v1/languages`. |
| R-81 | Review scoping resolves the active language's item-id set per call (two small queries). | ⚙ Fine at current scale; cache or push into the SQL query if the item bank grows very large. |

---
## Slice 25 — Feature-unlock roadmap (§7) (2026-08-03)

Practice features open up as a learner completes levels — §7's "these features will be unlocked
over time based on levels completed." This slice builds that mechanism and surfaces it as a
roadmap, so learners can see what they've unlocked and what's next.

**The schedule is a pure, tested rule.** `domain/feature_unlock.py` maps each feature to the level
it unlocks at, and exposes pure functions over it: `is_unlocked`, `unlocked_features` (monotonic —
the open set only grows), and `feature_states` (each feature with its unlock level, current state,
and how many levels remain). Unknown features are locked forever rather than silently available.
Reviews and reading are open from level 1; immersion mirrors the §16 "after level 10" rule. The
unlock levels are a clearly-labelled **filler** schedule — the spec says a CSV will define the real
ones, so it's a single dict to edit.

**"Completed" means completed.** `services/features.completed_levels` counts, in the learner's
*active language*, how many published levels have *every* item at Familiar or beyond — a partial
level doesn't count. That's the honest signal the schedule keys off, verified live: bringing one
of three items to Familiar leaves the level uncounted; finishing all of them advances the count and
unlocks the next tier of features.

**A reusable server-side gate.** `require_feature(db, user_id, feature)` 403s a locked feature with
its unlock level, so a practice entry point can enforce the gate rather than trusting the UI to
hide it (defense in depth). Wiring it into individual practice routes is incremental (R-82).

**Endpoint + roadmap page.** `GET /api/v1/features` returns `completed_levels` and each feature's
state; `/features` renders the roadmap with ✓ / 🔒 markers (never colour alone) and "unlocks at
level N (k to go)".

**No migration.** Pure logic over existing tables.

**Tests: ~712 → ~723 backend** (+~11: the pure schedule battery; the endpoint requires auth; a
fresh user has nothing completed; completing levels unlocks the right features; a partial level
doesn't count; the gate raises `feature_locked` with the unlock level) + ~151 → ~153 frontend
(+~2: features client + label helper).

**Next: the remaining polish items — paywall-gate reading/practice content (R-72/R-76), the 24h
practice-stage cadence (R-52), guided tours, dashboard-widget customization, and threading the
active language through stats/placement/reading (R-65/R-66).**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-82 | `require_feature` exists but isn't yet called by the practice routes (listening/speaking/etc.). | ⚙ Drop `require_feature(db, user_id=..., feature="listening")` into each practice start handler; the UI already shows lock state. |
| R-83 | The unlock levels are a filler schedule in `feature_unlock.py`. | ⚙ Replace the dict with the real per-feature unlock levels once the curriculum CSV defines them. |
| R-84 | "Completed" recomputes item→module→Familiar each call (a few queries). | ⚙ Fine at current scale; cache on `UserModuleState` or a materialized count if it gets hot. |

---
## Slice 26 — Settings & profile pages (§16, §20) (2026-08-03)

The account surfaces the header dropdown always promised: the `profile` and `settings` menu items
pointed at `/dashboard` as placeholders, and neither page existed. The `UserSettings` model already
carried every §16 field, so this slice is the missing service, endpoints, and pages — no schema
change.

**Settings validation is pure and tested.** `domain/settings.py` accepts only known fields, checks
each against its allowed values or range (rejecting `True` where an int is expected, out-of-range
batch sizes, unknown keys), and enforces the one real business rule — immersion mode can't be
turned on until it's unlocked (§16: "after finishing level 10"). It returns a cleaned patch or
raises with a per-field error map, so the client learns exactly what was wrong. Verified across the
full matrix, including multi-error accumulation and the immersion gate.

**Server-authoritative account service.** `services/account.py` get-or-creates the settings and
profile rows, applies only validated fields, converts `curriculum_mode` to its enum, and never
lets a client write server-controlled fields (xp, points, rank are read-only). The live run walks
defaults → update → persistence → the immersion gate (locked rejects, unlocked accepts) →
profile edit → get-or-create for a fresh user.

**Endpoints + pages.** `GET/PATCH /api/v1/me/settings` and `GET/PATCH /api/v1/me/profile` (auth
required; invalid settings → 422 with `field_errors`). `/settings` renders every §16 option grouped
into appearance / lessons / reviews / curriculum / answering / extras, each auto-saving on change
with an inline "saved ✓" and per-field error recovery; the immersion toggle is disabled until
unlocked. `/profile` edits name/bio/timezone and shows xp / rank / streak read-only. The header
dropdown's two items now open these pages.

**No migration.** Reuses `user_settings` + `profiles`.

**Tests: ~723 → ~739 backend** (+~16: the validation matrix; endpoints require auth; settings
defaults + update + persistence; invalid → field errors; the immersion gate over the API; profile
get/update; server-controlled fields stay read-only) + ~153 → ~156 frontend (+~3: account client).

**Next: remaining polish — apply the theme/font settings app-wide (a theme provider), guided
tours, dashboard-widget customization, and the deferred paywall/cadence threads.**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-85 | Settings persist, but `theme`/`font_size`/`color_theme` aren't yet applied app-wide (no global theme provider). | ⚙ Add a provider that reads `/me/settings` on load and sets a `data-theme`/font class on `<html>`; the values are already stored. |
| R-86 | Immersion mode is stored + gated, but the UI-translation layer that immersion drives (§16) is separate. | ⚙ Wire the immersion flag into the i18n layer when that lands; this slice only owns the toggle + gate. |
| R-87 | `immersion_unlocked_at` is read here but set elsewhere (level-10 completion trigger). | ⚙ Ensure the level-progression code stamps it at level 10 so the toggle actually opens. |

---
## Slice 27 — Appearance settings applied app-wide (§16) (2026-08-04)

Slice 26 stored `theme` / `font_size` / `color_theme`, but nothing consumed them — and `terraza`
was the only color theme. This slice makes appearance real: the settings take effect across the
app, dark mode works, and there are four color themes to choose from.

**Tokens became theme-driven.** The Terraza palette was hardcoded hex in `tailwind.config.ts`, so
`bg-terraza-*` compiled to fixed colours. It now reads `rgb(var(--terraza-*) / <alpha-value>)`, and
the `--lg-*` variables that drive the body background/grid alias the same variables — so both the
utility classes and the page chrome follow the active theme. The variables are RGB triplets, which
keeps opacity modifiers (`bg-terraza-danger/10`) working.

**A theme is two attributes.** `themes.css` defines each token per theme under
`[data-color-theme="…"]` and `[data-theme="dark"][data-color-theme="…"]`, so a dark override always
out-specifies its light block. Font size is a rem scale on `<html>`, so Tailwind's sizing scales
with it. Four color themes — **terraza** (adobe desert), **jacaranda** (lavender), **selva**
(jungle), **playa** (coastal) — each with a light and dark variant.

**The provider applies it.** `ThemeProvider` (wrapped around the app in the layout) paints the
cached appearance immediately on mount (no flash), reconciles with `/me/settings` once auth is
available, and — while the preference is "system" — follows OS light/dark changes live. The pure
`resolveTheme` (system → light/dark) is unit-tested; `applyAppearance` sets the `<html>` attributes,
guards against unknown values (falls back to terraza/md), and persists to localStorage. The settings
page's color-theme control is now a picker, and changing any appearance field applies instantly.

**No backend change.** `color_theme` was already a validated string; the UI simply constrains it to
the known themes now.

**Tests: ~156 → ~161 frontend** (+~5: `resolveTheme` for explicit/system/unknown; `applyAppearance`
sets attributes + persists, and falls back for unknown values; the color-theme list is exposed).
Backend unchanged at ~739.

**Next: guided tours, dashboard-widget customization, or the deferred paywall/cadence threads.**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-88 | The four palettes are Latin-America-inspired starting points; contrast isn't WCAG-audited yet, especially the dark variants. | ⚙ Run each theme through a contrast checker and nudge `ink`/`soft`/`accentInk` until AA passes. |
| R-89 | First paint uses the cached appearance from localStorage; a brand-new device shows the default theme until `/me/settings` returns (a brief flash possible). | ⚙ Add a tiny inline `<head>` script that reads localStorage before hydration if the flash is noticeable. |
| R-90 | `immersion_mode` (a separate §16 toggle) drives UI translation, not appearance; still pending its i18n layer (R-86). | ⚙ Unrelated to theming; tracked with the immersion work. |

---
## Slice 28 — Fix: appearance theming was monochrome (2026-08-04)

**Bug.** After slice 27 the whole app rendered black-on-white and theme switching did nothing —
even though fonts, spacing, and card shapes were fine.

**Cause.** Slice 27 pointed the Terraza tokens at CSS variables
(`bg-terraza-bg` → `rgb(var(--terraza-bg) / 1)`) and moved the variable *definitions* into a
separate `themes.css`. That stylesheet wasn't reaching the browser — most likely the
`import "./themes.css"` in `layout.tsx` didn't apply (the real layout had diverged from the shape
slice 27's patch expected, so that one patch silently SKIPPED while the token conversion applied).
With `--terraza-*` undefined, every colour resolved to an invalid `rgb()` and the browser dropped
it → default black text on a white page.

**Fix.** Define the theme tokens directly in `globals.css`, which is provably loaded (the fonts
prove it). `globals.css` now carries the full set — the default `:root` terraza palette, all four
color themes (terraza / jacaranda / selva / playa) with light + dark variants, and the font-size
scale — so colours resolve regardless of whether the separate `themes.css` ever loads. The fix
also re-ensures the `ThemeProvider` is wired (idempotent: skips if slice 27 already wired it; wires
it if not) so a saved theme is applied on load; if the layout has diverged too far to patch safely,
that step soft-notes with manual steps and colours still work.

**Verified** against a fixture reproducing the exact broken post-slice-27 state (globals.css
referencing undefined vars): after the fix every referenced `--terraza-*` is defined, braces
balance, all four themes carry light + dark, and the append is idempotent (byte-identical on
re-run). Also verified the clean case where slice 27 already wired the provider → layout reports
"already applied".

**No migration, no backend change.** Frontend CSS only.

**Lesson recorded:** theme tokens that Tailwind classes depend on must live in a stylesheet that's
guaranteed to load (i.e. `globals.css`), not in a separately-imported file whose import can be
missed by a patch or a divergence.

### Open questions (carried)

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-88 | Palettes still need a WCAG contrast pass, especially dark variants. | ⚙ Run each through a checker; nudge ink/soft/accentInk until AA. |
| R-89 | First paint uses cached appearance; a brand-new device shows default until /me/settings returns. | ⚙ Add a tiny inline `<head>` script if the flash is noticeable. |
| R-91 | `themes.css` is now redundant (its tokens live in globals.css). | ⚙ Harmless if still imported; can be deleted later along with its layout import. |

---
## Slice 29 — Landing page redesign (§20) (2026-08-05)

A complete rebuild of the public landing page as a scrollable, animated front door with a
multilingual theme.

**Structure.** A sticky nav (logo + log in / sign up), then four scroll sections: a **hero** with
the eyebrow, a headline whose greeting word rotates through ~18 languages ("say hola / kumusta /
こんにちは … to fluency"), a subheading, sign-up/log-in buttons, faint drifting greetings behind it,
and a horizontal marquee of hellos from around the world; an **SRS** section presenting the app's
five real tiers (beginner → fluent) as a climbing ladder; a **practice** section — an eight-card
grid (listening, speaking, reading, writing, sentence structure, verb conjugation, testing,
reviews); a **testimonials** section (three cards); a closing CTA; and a footer.

**Animation, no new deps.** All motion is CSS keyframes (appended to globals.css: float, bob,
marquee, sparkle, pop) referenced via inline `animation:` styles, plus an IntersectionObserver
`Reveal` wrapper that fades/rises each block as it enters view (staggered). Everything degrades
under `prefers-reduced-motion`: the globals.css reduce rule disables the keyframes/transitions, and
`Reveal` shows its content immediately (and also when IntersectionObserver is unavailable), so
content is never hidden behind motion.

**Content is a separate, testable module.** `lib/landing-content.ts` holds the greetings, SRS
tiers, practice features, and testimonials. The testimonials are clearly marked SAMPLE/PLACEHOLDER
copy — the only fabricated content, isolated for easy replacement before launch. Signed-in visitors
still redirect to their dashboard.

**Verified:** both `page.tsx` and the content module transform cleanly through esbuild (real JSX/TS
syntax check); content assertions pass (≥12 greetings incl. español + tagalog, the five SRS tiers
in order, the core practice surfaces, sample testimonials shaped as the page renders them). The
installer backs up the old landing page to `page.tsx.bak-slice29` before replacing it; keyframes
append idempotently.

**No migration, no backend change.**

**Tests: frontend +~4** (landing-content shape/coverage). The page itself is presentational.

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-92 | Testimonials are placeholder copy. | ⚙ Replace with real, consented quotes (and photos/initials) before launch. |
| R-93 | Footer links point at /pricing, /changelog, /support, /faq. | ⚙ Fine if those routes exist; otherwise wire them up or trim the footer. |
| R-94 | Greeting fonts: some scripts (Arabic, Thai, Devanagari) rely on system fonts, not the bundled UI font. | ⚙ Acceptable for decoration; add web fonts for those scripts if you want them on-brand. |

---
## Slice 30 — Auth UX: header, password policy, social buttons (§20, §25) (2026-08-05)

A batch of auth-surface changes.

**Solid header.** The landing nav was translucent (`bg-terraza-bg/80 backdrop-blur`); it's now a
solid `bg-terraza-bg` to match the footer.

**No Spanish subheading.** Removed the `empieza tu viaje` / `bienvenido de nuevo` `<h1>` from the
shared auth form — the polyglot logo and the English subtext remain.

**Password policy (§25).** New pure rules in `domain/password.py`: at least 8 characters plus an
uppercase, a lowercase, a number, and a special character (space doesn't count). `check_password`
drives a live requirements checklist under the signup field; `validate_password` raises listing
what's missing. It's enforced at the **signup route** (422 `weak_password`) rather than in
`create_account`, so seeding and admin-created users aren't affected — only public signups. The
frontend mirrors the rules and blocks submit early. **Heads-up:** any existing test/seed that
signs up via the API with a weak password (e.g. `supersecret1`) will now get 422 — update those
fixtures to a compliant password like `Supersecret1!`.

**Social sign-in buttons (§20).** Google / Discord / GitHub buttons now sit below the sign-in
button on the shared form (so both login and signup show them). They always render, but a provider
only navigates once the backend reports it configured; until then a click shows an honest "coming
soon" note — no login is faked. The new `GET /api/v1/auth/oauth/providers` reports which providers
have credentials in the environment (all false by default), and `/{provider}/start` 404s unknown
providers, 503s unconfigured ones, and 501s configured-but-unwired ones.

**Email verification — options (not yet implemented).** This one changes the core signup flow, so
it's called out for its own slice. Options considered:
- **Auth.js (NextAuth) Email provider / verification** — fits the stated stack; sends a magic
  link, and pairs naturally with the social providers. Biggest change (moves auth into Auth.js).
- **Custom token flow on the current API** *(recommended)* — signup creates the user as
  `pending`, stores a hashed, expiring verification token, and emails a link to
  `/verify?token=…`; the verify endpoint marks the email verified and issues the session, so the
  learner lands signed in. Reuses the existing mail path (Mailpit in dev) and JWT sessions; small,
  testable, no architecture change.
- **Managed provider** (Supabase Auth email confirmations, or Clerk/Auth0) — least code, but hands
  identity to a third party.
Recommendation: the custom token flow — it's the smallest, most testable step and keeps auto
sign-in on verify. Deliver it as slice 31 (needs a migration + the mail-service shape).

**No migration, no schema change this slice.**

**Tests: backend +~8** (password rules; signup rejects weak / accepts strong; oauth providers
default-false, env-configured, start 503/404) + **frontend +~7** (password checklist rules, space
not special; oauth helpers).

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-95 | Existing weak-password test/seed fixtures now fail signup. | ⚙ Find-replace API signup passwords to a compliant one (e.g. `Supersecret1!`). |
| R-96 | Social buttons show "coming soon" until OAuth is wired. | ⚙ Implement per-provider adapters (authorize redirect + callback token exchange) and set the client id/secret env vars. |
| R-97 | Email verification is designed but not built. | ⚙ Implement the recommended custom-token flow next (migration + mail + /verify page + auto sign-in). |

---
## Slice 31 — Dashboard launch + Customize Lessons (§20, by request) (2026-08-06)

First slice of a larger dashboard/lesson/practice batch. This one covers the dashboard launch
changes and the Customize Lessons page; the lesson-session UI rework and the practice
playground + admin sandbox follow in their own slices.

**Dashboard.** The "welcome back {name}" card now sits **above** the lesson/review actions
(previously it was the first cell of the widget grid). And the two action cards are no longer one
big clickable card each — a new `DashboardActions` component gives them explicit buttons: reviews →
**start reviews**; lessons → **start lessons** + **customize lessons**. Disabled/empty states are
honest (e.g. "keep reviewing to unlock the next level"). `widgets.tsx` is left untouched — the old
`ActionButtons` is simply no longer imported by the dashboard.

**Customize Lessons page** (`/lessons/customize`). Per-level sections list the published items the
learner hasn't started yet; each item is a clickable chip you add to the batch (✓/+ marker, never
colour alone). Next to each "level N" heading a filter regroups that level's items —
**grammar/vocab · theme · random** — and the chips ease into their new buckets (a CSS position
transition). A **begin lesson** button sits at the bottom and, until you scroll to it, a
semi-transparent copy sticks to the bottom of the viewport (IntersectionObserver sentinel).

- Backend: read-only `GET /api/v1/lessons/selectable` → `services/custom_lesson.selectable_items`,
  which lists not-yet-started published items in the **active language**, grouped by level, with
  term / translation / item type / part-of-speech. No writes, no planner side-effects — safe on a
  GET. Verified live: excludes started + draft items, groups by level, correct fields, empty for a
  language with no content.
- The grouping is a pure, tested helper (`groupItems`): type → vocab/grammar; theme → part-of-speech
  (a **proxy** until real lesson themes are stored — flagged below); random → one seeded, stable
  shuffle. Empty groups are dropped.

**First-cut scope on "begin lesson":** it remembers the selection (sessionStorage) and enters the
lessons flow. Binding the exact selected set into a custom teach → quiz → SRS session needs a
custom-lesson backend that mirrors the existing lesson-complete's SRS-init + XP ledger exactly;
that's the next lesson-session slice, done carefully rather than guessed.

**No migration, no schema change.**

**Tests: backend +~3** (selectable requires auth; lists unstarted items by level; service unit) +
**frontend +~4** (groupItems: type/theme/random/deterministic/empty-drop).

### Remaining in this batch (upcoming slices)
- **Lesson-session rework:** stationary bottom back/next, "say it" moved to the bottom, centered
  50%-transparent card, details/reading/examples tabs with scroll-spy mini-header + back-to-top,
  ←/→ hotkeys, and the end-of-lesson-quiz enter-to-advance fix.
- **Practice playground:** categorized layout, bigger header, testing + reading moved from the
  header into practice.
- **Admin sandbox:** everything unlocked so all practices are testable.

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-98 | The "theme" filter groups by part-of-speech, not real lesson themes (food/travel/…), which aren't stored per item. | ⚙ Add a `theme`/`lesson_batch` label to items (or surface the planner's lesson title without its write side-effect), then group by it. |
| R-99 | "begin lesson" enters the standard lessons flow; the selected set isn't yet taught as a custom session. | ⚙ Add `POST /lessons/custom/{start,complete}` reusing the lesson-complete SRS-init + XP ledger; wire the runner to the stored selection. |
| R-100 | Selectable lists items across all levels regardless of unlock state. | ⚙ If desired, hide locked levels' items (compute unlock like the levels page) — or leave visible as a "what's ahead" preview. |

---
## Slice 32 — Practice playground + Admin sandbox (by request) (2026-08-09)

Second slice of the dashboard/lesson/practice batch. Lesson-session rework (stationary
back/next, details/reading/examples tabs, hotkeys) is still its own upcoming slice.

**Practice playground** (`/practice`). Rebuilt from one flat grid into three labelled,
colour-tinted sections — **drills** (fill in the blank, verb conjugation, weak items, listening,
speaking), **test yourself** (the three testing maps: cefr, app, life), **read** (the reading
library) — so a learner finds what they want by section instead of reading every card. The
`testing` and `reading` links are gone from the header nav; they're practice tiles now, still
pointing at the same `/tests` and `/reading` routes. The page `<h1>` is bigger (`text-3xl` /
`sm:text-4xl`, up from `text-2xl`) to read as the hub it now is.

**Admin sandbox** (`/dev`). This already existed — "unlock all items" / "make reviews due now" /
SRS time-scale controls, gated on the `dev_panel` capability — but was unreachable: no link to it
anywhere in the UI, and it 500'd on load. Fixed both: the account-menu dropdown now shows
"dev sandbox" for accounts with `dev_panel` (right under "admin"), and the page loads. Verified
live: unlock-all populated 524 items and a previously-empty drill (`weak items`) immediately had
real material.

**Unrelated regression fixed in passing.** `/dev`'s crash wasn't new — it was the same pattern as
the `/decks` crash fixed earlier this batch: a prior commit (Stripe billing, `95e4192`) overwrote
`billing-api.ts` wholesale and dropped the `dev`/`DevState` export the page depended on. Restored
it as its own `lib/dev-sandbox-api.ts` (mirroring `lib/decks-api.ts`) rather than back into
`billing-api.ts`, so a future rewrite of that file can't collide with it again. Backend contract
(`/api/v1/dev/*`) was untouched and still matches.

**No migration, no schema change.**

**Tests:** none added — no new pure logic to unit-test; verified live in a headless browser
(practice sections render, header no longer has testing/reading, `/dev` typechecks, loads, and
its two main actions complete without console errors).

### Remaining in this batch (upcoming slice)
- **Lesson-session rework:** stationary bottom back/next, "say it" moved to the bottom, centered
  50%-transparent card, details/reading/examples tabs with scroll-spy mini-header + back-to-top,
  ←/→ hotkeys, and the end-of-lesson-quiz enter-to-advance fix.

### Known pre-existing breakage (not fixed, out of scope this slice)

Same overwrite pattern as `/decks` and `/dev`, still broken: `/reset-password` and `/verify-email`
call `account.forgotPassword` / `resetPassword` / `verifyEmail`, none of which exist on the current
`account-api.ts` (rewritten for settings/profile in `449ba08`) — and per R-97 above, the backend
routes they'd call don't exist either, so this needs the verification flow built, not just a client
restore. `auth-form.tsx` also has an unrelated pre-existing type error (`onboarding_completed` on
`never`). Flagged for a future slice.

---
## Slice 33 — Lesson-session rework (by request) (2026-08-09)

Third and last slice of the dashboard/lesson/practice batch, scoped to the teaching phase of
`/levels/[level]/lessons/[lesson]` (the quiz phase's layout is unchanged, aside from the enter-fix
below).

**The card.** `ItemCard` is restructured into a pinned block (type tag, term + audio, translation
— fixed content, so it never changes height) and a scrollable info area below it, ending in three
tabs — **details / reading / examples** — sitting on the card's bottom border. Clicking a tab
`scrollIntoView`s its section; each section has `scroll-mt-24` so it lands cleanly under the
sticky mini-header. Background is the same card colour at 50% opacity with a light backdrop-blur
(`bg-terraza-card/50 backdrop-blur-sm`) so it stays legible over the page's background pattern.

- **details**: part of speech, article, gender, structure, meaning, explanation — whichever the
  item has.
- **reading**: the pronunciation guide that used to be inline under the term ("say it: …", IPA) —
  moved here instead of floating mid-card, which was the actual source of the layout jumping
  around, not just the buttons.
- **examples**: sentence links, fetched on demand via the existing `GET /api/v1/items/{type}/{id}`
  (same endpoint the item-detail page already uses for this) and cached per item so flipping back
  doesn't refetch. No backend changes — the data and the endpoint already existed, just unused
  here.

**Stationary back/next.** Pulled out of the card's flow entirely into a fixed bar at the bottom of
the viewport (`fixed inset-x-0 bottom-0`), so a taller card never moves them — this is what
actually fixes "the buttons move around," structurally, rather than just reducing how often it
happens.

**Scroll behavior.** A sentinel sits right after the pinned block; once it scrolls out of view
(`IntersectionObserver`), a sticky mini-header appears at the top of the viewport showing the
current item's term + translation, and a "↑ top" button appears fixed bottom-right. Changing items
resets the tab to `details`, resets scroll to the top, and re-arms the sentinel.

**Hotkeys.** ← / → mirror the back/next buttons exactly, including → becoming "quiz me" on the
last item — same function the button's `onClick` calls, not a separate reimplementation. Guarded
against modifier keys and against firing while a text input has focus (there isn't one in the
teaching phase, but the guard costs nothing and matches the pattern in `use-enter-advance.ts`).

**Quiz enter-to-advance.** The lesson's end-of-lesson quiz never adopted `useEnterAdvance` — the
hook reviews already uses to let Enter both submit and then advance. One line
(`useEnterAdvance({ active: phase === "quizFeedback", onAdvance: nextQuiz })`) closes the gap; the
"continue" step now works exactly like reviews' feedback step.

**No migration, no schema change.**

**Tests:** none added — this is layout/interaction wiring over existing data, not new pure logic.
Verified live in a headless browser: card renders (empty and populated details/reading/examples
states), tab-click scroll, ←/→ navigate and correctly hand off to "quiz me" on the last item,
mini-header + back-to-top appear/disappear correctly at realistic and edge-case viewport heights,
and the second Enter now advances past quiz feedback (confirmed by the input reappearing, not by
the queue count — a wrong answer cycles to the back of the queue without changing its length, which
would have been a false negative).

### Batch complete

This closes out the dashboard/lesson/practice batch started at Slice 31: dashboard launch +
Customize Lessons (31), Practice playground + Admin sandbox (32), Lesson-session rework (33).
Remaining open items are tracked above (R-98–R-100) and in "Known pre-existing breakage" — none of
them block this batch, they're pre-existing or deliberately deferred.

---
## Slice 34 — Replay-onboarding dev tool + curriculum step after onboarding (by request) (2026-08-09)

**Replay onboarding** (`/dev`). A narrower sibling to "reset my progress": clears only
`profile.onboarding_completed_at` (`services/dev_sandbox.replay_onboarding`, new
`POST /api/v1/dev/replay-onboarding`, `dev_panel`-gated like every other sandbox route). XP, SRS
progress, streaks, active language, curriculum_mode — all untouched, unlike the full reset. The
button calls it and immediately routes to `/welcome`. Backend tests: forbidden for a normal user;
owner replay clears the flag while `xp_total` (set to a non-zero value first) is confirmed
unchanged after.

**Curriculum step after onboarding.** The signup → onboarding order was: choose-language, then the
5 slides, then straight to the dashboard. By request, reordered so a learner sees *why* the method
works before *what* to set up: **slides → choose-language → choose-curriculum (new) → dashboard**.
`choose-curriculum` is a new page presenting the three existing `curriculum_mode` values
(`default_dispersed`/`grammar_batch`/`fully_dispersed`, already used by the settings page — no
backend or schema changes) as onboarding-style cards with friendly labels — **themed / batched /
mixed** — and the current value pre-selected. Meaningful timing, not just placement: curriculum
mode locks in per-level the first time a lesson from that level is planned (PLANNING §5), so
onboarding is the one guaranteed moment it's still free to pick for every new learner, rather than
a setting most people never find. Saves via the same `PATCH /api/v1/me/settings` the settings page
already uses.

Returning-user login is unaffected — that branch already routed to `/welcome` when
`onboarding_completed` is false and `/dashboard` otherwise; the new steps just chain naturally off
of `/welcome`'s completion, in either the fresh-signup or the dev-replay case.

**No migration, no schema change.**

**Tests: backend +2** (replay-onboarding forbidden/owner-clears-without-touching-xp). No new
frontend unit tests — this is routing + a static options list, not new pure logic; verified live
in a headless browser instead: a full fresh signup driven through the real UI (fill form → 5
slides → pick a language → pick a pacing mode → lands on `/dashboard`, zero console errors), and
the dev button's full round trip (`onboarding_completed` true → click → redirected to `/welcome` →
confirmed false via `/me`, then restored).

**Found and fixed in passing, while getting a clean test baseline for the above:** two pre-existing
bugs in `tests/test_feedback_onboarding_db.py`, unrelated to this slice but blocking verification
of it:
- The file's weak `"supersecret1"` signup password now fails the strong-password policy added in
  an earlier slice — this is the exact fixture staleness R-95 already flagged. Fixed in this file
  (`Supersecret1!`); the same staleness likely exists in other test files R-95 didn't enumerate —
  out of scope here.
- Three tests (`test_admin_lists_and_filters_and_responds`, `test_owner_reset_clears_onboarding`,
  and now my own new replay test copied from the same pattern) called `_signup` **twice** for the
  same email to get a token reflecting a role promoted mid-test — signup 400s on a duplicate email,
  so this always failed once it got past the password issue. Added a `_login` helper and switched
  the second call to it. All 12 tests in the file pass now.

**Known, not fixed:** a full `pytest -q` run still shows ~100 failures / 134 errors across the
wider suite (the same weak-password staleness elsewhere, plus an unrelated `KeyError` affecting
`test_practice_db.py`/`test_speech_practice_db.py`/parts of `test_learn_flow_db.py`). Untouched —
well outside this slice's scope, flagged for its own cleanup pass.

---
## Slice 35 — Handwritten hero greeting (§20 landing) (2026-08-09)

The landing hero's rotating word ("say **hola** / **kumusta** / **bonjour** … to fluency") is now
*written* rather than popped in: each greeting's glyphs ink in one at a time, left→right, behind a
small travelling pen nib, then the word is held and **erased** by a wipe (with a little eraser
sliding across) before the next language is written in its place. It cycles through the full
multilingual `GREETINGS` list.

**Why a small in-house engine, not a handwriting npm package.** The greetings span many scripts —
español, tagalog, 日本語, 한국어, 中文, العربية, हिन्दी, ไทย, русский … — and the popular
handwriting libraries (Vara et al.) ship Latin-only stroke fonts, so every non-Latin greeting would
fail to render. A per-glyph "ink-in + wipe-erase" reveal is script-agnostic, needs no font data,
and keeps the landing page's "CSS-only animation, no new deps" rule from slice 29. If a true cursive
stroke engine is ever wanted per language, the seam lives in `lib/handwrite.ts`.

**Structure.**
- `lib/handwrite.ts` — pure, deterministic helpers: `graphemes()` (Intl.Segmenter with an
  Array.from fallback, so 你好 / नमस्ते / emoji split by *visual* cluster, never mid-surrogate),
  `writeMs` / `cycleMs` / `charDelays` (timing), and `dirFor` (Arabic/Hebrew → rtl). No DOM, no
  React → unit-tested like `landing-content.ts`.
- `components/handwritten-greeting.tsx` — `<HandwrittenGreeting/>` runs the write→hold→erase→next
  cycle off those timings.
- `app/globals.css` — appended keyframes (`hw-write-in`, `hw-write-in-rtl`, `hw-erase`, `hw-nib`,
  `hw-eraser`), idempotent behind a slice-35 marker.
- `app/page.tsx` — the rotating `<span>` in the `<h1>` is swapped for `<HandwrittenGreeting/>`; the
  Hero's own rotation state/effect is removed (the component owns it now).

**Accessibility.** The animated glyphs are `aria-hidden`; a stable, screen-reader-only word
("hello") keeps the headline reading "say hello to fluency" no matter which language is on screen.
Under `prefers-reduced-motion` there is **no** writing/erasing — the plain word is always fully
visible and simply cross-rotates on a slow timer (content never hidden behind motion, the slice
27–29 lesson). RTL greetings reveal right→left.

**Verified.** All four new files transform cleanly through esbuild (real TS/TSX syntax check); the
pure logic was executed in Node to confirm every assertion (grapheme round-trips across six scripts,
नमस्ते → 3 clusters vs 6 code points, monotonic delays ending exactly at `writeMs`, cycle math,
rtl detection). The `page.tsx` patcher was tested against a faithful fixture for correctness +
idempotency, and against a diverged file to confirm it **aborts without writing** (exit 2) rather
than half-applying — the silent-SKIP failure mode from slices 27–28.

**No migration, no backend change.** Frontend only.

**Tests: frontend +~10** (`handwrite.test.ts`: grapheme/timing/direction; `handwritten-greeting.test.tsx`:
a11y label + reduced-motion render).

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-98 | The "ink-in + wipe" reveal reads as *writing*, but isn't literal cursive stroke-drawing. True per-letter cursive would need single-stroke SVG paths per glyph (Latin) or a multi-script stroke font — heavy and Latin-biased. | ⚙ Ship the reveal now; if a specific hero word (e.g. "hola") should truly draw stroke-by-stroke, add an optional SVG-path variant for that one word behind the same component seam. |
| R-99 | Timing (`DEFAULT_TIMING`) is a filler feel: 55ms/glyph stagger, 260ms ink, 1.1s hold, 650ms erase. | ⚙ Tune in `lib/handwrite.ts`; nothing else depends on the values. |
| R-100 | The travelling pen nib is shown for LTR only; RTL greetings ink in without the nib. | ⚙ Add an rtl nib track (mirror `hw-nib`) if the nib should appear for Arabic too. |

---
## Slice 36 — Hero greeting is now *drawn* like handwriting (§20 landing) (2026-08-09)

Follow-up to slice 35. That version *revealed* each greeting (glyphs faded/clipped in behind a
pen-nib emoji); the ask was for it to actually look **written**. This replaces the reveal with a
true stroke draw-on: each "hello" is real single-stroke cursive, and its strokes are inked in with
`stroke-dashoffset`, one after another at a constant pen speed, so a line travels across the word
and writes it. After a hold it erases (strokes un-draw left→right, like a wipe) and the next
language is written. **No emojis anywhere** (the nib/eraser glyphs are gone).

**How the handwriting is real, with no runtime dependency.** `lib/hero-strokes.ts` is a GENERATED,
clearly-marked data file: single-stroke cursive path data (viewBox + per-letter path `d`, translate,
and stroke length) for a curated set of greetings, baked **offline** from the public-domain Hershey
"cursive" single-line font via the `hersheytext` toolkit. Only the static path data ships — no font,
no `opentype.js`, no npm handwriting library at runtime, keeping the slice-29 "CSS-only animation,
no new deps" rule. `scripts/gen-hero-strokes.cjs` regenerates it (manual, off-CI:
`npm i --no-save hersheytext svg-path-properties && node scripts/gen-hero-strokes.cjs > lib/hero-strokes.ts`).

Why curated words: single-stroke cursive fonts are Latin-script, so the drawn set is Latin greetings
(español + tagalog first, then français/italiano/deutsch/türkçe/kiswahili/hawaiian/português). The
non-Latin hellos (日本語, 한국어, 中文, العربية …) have no single-stroke glyphs and stay in the
marquee / floating greetings, where they already live — so nothing multilingual is lost.

**Pieces.**
- `lib/handwrite.ts` — rewritten to the constant-speed model: `writeMs` / `eraseMs` / `cycleMs`
  and `strokeSchedule(lens, totalMs)` (each stroke gets a time slice ∝ its length, back-to-back, so
  the pen speed is constant across uneven letters). Pure → unit-tested.
- `components/handwritten-greeting.tsx` — rewritten to render an inline SVG sized from the headline
  font-size (`em`), drawing strokes via `hw-draw` and un-drawing via `hw-undraw`, with per-stroke
  delay/duration set inline. Colour is `currentColor` (inherits the accent).
- `app/globals.css` — appended `hw-draw` / `hw-undraw` keyframes (idempotent, slice-36 marker). The
  slice-35 keyframes are now unused but harmless.
- `app/page.tsx` — the hero call drops its now-unneeded `greetings` prop
  (`<HandwrittenGreeting label="hello" />`); `GREETINGS` stays imported for the marquee/floating use.

**Accessibility unchanged.** Drawn SVG is `aria-hidden`; a stable sr-only "hello" keeps the headline
reading "say hello to fluency". Under `prefers-reduced-motion` the word renders **fully drawn and
static** (still the cursive look) and swaps on a slow timer — never hidden behind motion.

**Verified.** All six files transpile through esbuild; the timing logic was executed in Node against
every assertion (constant-speed schedule, back-to-back with no gaps, last stroke ends exactly at
totalMs, safe on empty/zero). The stroke data was rendered to PNG at write-progress **and**
erase-progress points to confirm it visibly writes left→right and erases left→right (kumusta:
`kum`→`kumusta`, then `usta`→`a`). The generator's letter-coverage check passes for every curated
word (no missing glyphs). Both patchers (page prop-drop) were tested for idempotency and
abort-without-writing on divergence.

**Tests: frontend +~20** (`handwrite.test.ts` timing, `hero-strokes.test.ts` data integrity,
`handwritten-greeting.test.tsx` a11y + reduced-motion + no-emoji). **No migration, no backend
change.**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-98 (resolved) | "make it look written." | ✔ Real single-stroke draw-on shipped. |
| R-101 | Drawn set is Latin-script only (single-stroke font limitation). | ⚙ If a specific non-Latin hello must also *draw*, hand-author its single-stroke SVG and add it to `hero-strokes.ts`; the component already renders whatever's in the array. |
| R-99 | Pen feel is filler: `PEN_SPEED=0.19` (len/ms), `HOLD_MS=1200`, `ERASE_RATIO=0.55`. | ⚙ Tune in `lib/handwrite.ts`. |
| R-102 | Word width shifts "to fluency" as different-length words cycle (same as before). | ⚙ Reserve the widest word's width if the reflow reads as jumpy. |

---
## Slice 37 — Refine the handwritten hero (Option A) (2026-08-09)

Slice 36 drew the greeting correctly but it read as a faint hairline scribble at ~half the height
of the headline (a screenshot caught it mid-write and looking weak). This is a pure-refinement pass
— no new mechanism, no new deps — fixing the three things that made it look thin and small:

1. **Marker-weight stroke that scales.** The pen was a fixed 1.3px non-scaling stroke (hairline at
   any size). Now it's `STROKE_UNITS = 2.1` font units with **no** `non-scaling-stroke`, so it
   renders as a confident marker line that scales with the word. (Verified against the headline at
   64px: 2.1u matches the bold "say … to fluency" weight; 1.6u was thin, 2.6u heavy.)
2. **Sized to the headline.** A shared `EM_PER_UNIT = 0.043` maps font units → em, so a word's
   height is `vb.h * EM_PER_UNIT` and its ascenders reach the headline's cap height. The scale is
   **constant** across words, so words with ascenders/descenders are correctly taller — like real
   writing — instead of every word being squeezed to one box height.
3. **Correct baseline + slower pace.** `hero-strokes.ts` is regenerated so each word's viewBox
   **bottom is the shared baseline** (`BASE_Y`, detected as the most common letter-bottom); the
   inline SVG uses `vertical-align: baseline` so it sits on the text baseline, and descenders (the
   `j` in "bonjour"/"jambo", `descend` units below) hang below via `overflow: visible`. Timing is
   slowed for legibility: `PEN_SPEED 0.19 → 0.14`, `HOLD_MS 1200 → 1600`, `ERASE_RATIO 0.55 → 0.6`.

**Pieces.** `lib/hero-strokes.ts` regenerated (baseline-cropped viewBox + `descend`, and new
exported `BASE_Y` / `EM_PER_UNIT` / `STROKE_UNITS`); `lib/handwrite.ts` retuned; component sizes via
`EM_PER_UNIT`, draws the scaling stroke, aligns to baseline, and accepts optional `scale` /
`strokeUnits` overrides; `scripts/gen-hero-strokes.cjs` updated to emit the baseline + constants.
No `page.tsx` change (the hero call is unchanged; the component API is backward-compatible). No CSS
change — the slice-36 `hw-draw`/`hw-undraw` keyframes are reused; the installer only re-adds them if
they're somehow absent (so slice 37 is safe to apply even without 36).

**Verified.** All six files transpile; timing executed in Node with the new defaults (constant-speed
schedule, back-to-back, last stroke lands exactly on time); data invariants checked (every word's
`vb` bottom == `BASE_Y`, aspect matches, bonjour descends / hola doesn't). The at-scale hero mock
("say ⟨word⟩ to fluency" at 64px) confirmed the word now matches the headline weight and size, sits
on the baseline, and hangs the `j` below.

**Tests: frontend ~same count, updated** (`handwrite.test.ts` new defaults + schedule;
`hero-strokes.test.ts` baseline/scale constants + `vb`-bottom==BASE_Y + descent invariants;
`handwritten-greeting.test.tsx` scaling-stroke + baseline assertions). **No migration, no backend
change.**

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-99 (updated) | Feel is filler: `PEN_SPEED=0.14`, `HOLD_MS=1600`, `ERASE_RATIO=0.6`, `EM_PER_UNIT=0.043`, `STROKE_UNITS=2.1`. | ⚙ Tune in `lib/handwrite.ts` (pace) and `lib/hero-strokes.ts` (size/weight), or per-instance via the component's `scale`/`strokeUnits` props. |
| R-103 | Still a geometric cursive, not literally the owner's hand. | ⚙ Option B on the table: a small local capture tool to record real handwriting as SVG and bake it into the same pipeline. |
| R-102 | "to fluency" shifts as different-width words cycle. | ⚙ Reserve the widest word's width if the reflow reads as jumpy. |

---
## Slice 38 — Curriculum import accepts real-world CSVs (§22/§24) (2026-08-10)

**Problem.** The owner's grammar sheet (`Spanish_Stuff_-_Grammar__2_.csv`, 187 rows) imported as
"0 created" with no obvious reason. Root cause: the grammar parser reads the term from a column
named `Grammar` (the original sheet used `Grammar ,Translation,Structure,Level,PoS,…`), but the new
sheet puts the term under **`Word`** and the gloss under **`Meaning`**, leaving `Translation`/`PoS`
blank. So every row's title read as empty and was silently skipped; imported as "vocabulary" instead,
all 187 rows hard-failed because vocab requires `Translation`.

**Fix — forgiving header aliasing (pure parser, `curriculum_csv.py`).**
- New `_AliasReader` remaps recognised headers (case-insensitive, space-tolerant, plus synonyms:
  Word/Grammar/Term/Item, Level/Unit/Module, Batch/Lesson, PoS/"Part of Speech"/"Word Type",
  Structure/Pattern, Meaning/Notes/Description, Variants/Variations, Castilian/Spain, …) to the
  canonical names the parsers already read. Unknown columns pass through untouched; a detected term
  column is exposed under both `Word` and `Grammar ` so either parser finds it.
- **Grammar** now falls back to `Meaning` for the gloss when `Translation` is blank (anchored to the
  grammar-specific translation+structure block so the identical **vocabulary** translation line is
  left untouched — vocab still hard-requires `Translation`, preserving existing tests).
- A missing term column now yields a clear `columns` error ("No term column found… see the
  template") instead of a silent 0-row import.
- The 187 per-row "missing structure" warnings are aggregated into a single line.

**Verified against the real file.** All 187 rows import, 0 errors, gloss pulled from Meaning
(y→and, con→with, "no + conjugated verb"→"Basic negation."), levels 1–16 (L16 has 7 — a real note).
Also verified: a vocab sheet with `Term`/`Unit`/`Lesson` headers imports; a file with no term column
surfaces the `columns` error; unknown columns are ignored; the patched module `py_compile`s; both
patchers are idempotent and abort-without-writing on divergence.

**Also shipped**
- Starter templates at `apps/web/public/templates/{vocabulary,grammar}-template.csv` (parse with 0
  errors), linked from the import panel.
- Admin import panel now shows the required columns per kind, notes the aliases, and links the
  templates (anchored insert, esbuild-verified).
- `docs/CSV_IMPORT.md` — the full valid-CSV reference, incl. "re-import = edit/move" (import is
  idempotent on (level, normalised term), so editing `Level`/`Batch` and re-importing **moves** an
  item; changing cells **edits**; adding rows **adds** — the CSV doubles as an editor until the
  in-app editor lands).
- Tests: `tests/test_importer_aliases.py` (Word-header grammar + Meaning gloss; aliased vocab
  headers; missing-term-column error; unknown columns ignored; aggregated structure warning).

**No migration, no schema change.** Parser + UI copy + docs + tests only.

### Deferred to Slice 39 — in-app curriculum editor (the rest of the ask)

The point-and-click side of "fully edit / delete / add / move into any unit or batch" is the next
slice: `POST/PATCH/DELETE /admin/content/{vocabulary,grammar}` (+ `/move` and `/restore`), Pydantic
validation, audit logging + soft-delete (§22), and an admin editor UI with an edit form, archive/
restore, and level/batch move (drag-and-drop with a keyboard-accessible selector fallback, §29).
Split out so the import fix ships now, fully tested, rather than waiting on the larger UI.

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-104 | Grammar `Batch` (all 5 in the sheet) isn't stored on `GrammarPoint` (grammar is one batch/level). | ⚙ Fine for now; the in-app editor (S39) can expose batch if grammar ever needs sub-batches. |
| R-105 | Alias list is a fixed table. | ⚙ Extend `_HEADER_ALIASES` as new sheet shapes appear. |
| R-106 | L16 grammar has 7 points (not 12); levels beyond 5 previously had no grammar. | ⚙ Real content gap — flagged as a warning, not fabricated. Fill via the sheet. |

---
## Slice 39 — In-app curriculum editor: CRUD + move (§22/§24) (2026-08-10)

The point-and-click side of "fully edit / delete / add / move into any unit or batch." Follows
slice 38's import fix. Admins can now manage vocabulary and grammar directly in the app, not just
via CSV.

**Schema.** Vocabulary stored its level (via `module_id`) but had **no batch** column — the CSV
`Batch` was read and dropped — so "move to a batch" wasn't representable. Added
`vocabulary_items.batch` (Integer, NOT NULL, default 1). The migration is generated at install time
by `gen_migration.py`, which computes the current Alembic **head from the version files** (pure file
parsing, no DB) and chains to it, aborting if it can't find exactly one head — so it never risks a
broken `alembic upgrade head`. The importer's `_apply_vocab` now persists batch, so CSV round-trips
place items in the right batch too.

**Backend API** (appended to the admin router; capability-gated + audit-logged, §22):
- `GET /admin/content/{vocabulary,grammar}/editor` — editor list incl. batch, status, archived
  (separate from the summary list so `ContentItemOut`/schemas were untouched).
- `POST /admin/content/{vocabulary,grammar}` — create (draft).
- `PATCH /admin/content/{vocabulary,grammar}/{id}` — edit fields.
- `POST /admin/content/{vocabulary,grammar}/{id}/move` — move to any level (+ batch for vocab);
  creates the target module if it doesn't exist yet.
- `DELETE …/{id}` — **soft delete** (sets `deleted_at` + `archived`; needs `content_archive`).
- `POST …/{id}/restore` — un-archive back to draft.
Create/edit/move need `content_edit`; archive/restore need `content_archive`. Permanent deletion
stays owner-only (`permanent_delete_approve`) in the archives view — not built here.

**Validation.** Pure `app/domain/content_edit.py` (level 1–200, batch 1–4, non-empty term, article/
gender enum membership, and the §6 rule that only nouns carry an article — non-nouns are coerced to
`none/none`, matching the DB CHECK constraint). Pydantic `Field` bounds on every request body.

**Frontend.** New `/admin/curriculum` page: kind tabs (vocab/grammar), level filter, add form,
per-row **edit** (inline form), **move** (level select, plus batch select for vocab), **archive**,
and **restore** (with a "show archived" toggle). All four states — loading / empty / error / success
(toast). Controls are native selects/buttons (keyboard-accessible, §29); drag-to-move is deferred
polish. New `lib/editor-api.ts` client; a link added to the admin page (editor also reachable
directly).

**Verified.** Pure validators executed (all pass). The appended route block, the generated
migration, both model/importer patchers, and both test files `py_compile`. The migration generator
was exercised on a fake versions tree: chains to the real head, is idempotent, and aborts on
multiple heads. Editor page + client transpile through esbuild; the admin-link patch output
transpiles. All patchers are idempotent and abort-without-writing on divergence.

**Not runnable here:** the DB integration tests (`tests/test_admin_editor_db.py`) need the project's
testcontainers Postgres — they run in CI. They're written to the existing admin-test patterns
(signup → elevate role → call routes) and cover CRUD, move, batch, soft-delete/restore,
capability gating (a moderator with `admin_panel` but not `content_edit` gets 403), and audit writes.

**Tests: backend +~12** (`test_content_edit.py` pure validation, runnable now; `test_admin_editor_db.py`
integration). Frontend: editor page (states + move + edit) — component test to add in CI.

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-107 | Move UI uses level/batch **selects**, not drag-and-drop. | ⚙ Selects are fully functional + accessible now; add DnD (with these selects as the keyboard fallback, §29) as polish later. |
| R-108 | Level picker caps at 20 in the UI (`LEVELS`). | ⚙ Cosmetic cap; raise or make it a free number input if levels exceed 20. |
| R-109 | Editor edits core fields; the full item schema (accepted/rejected answers, example sentences, audio) isn't exposed yet. | ⚙ Add an "advanced" section per item in a later slice; the API already stores these. |
| R-110 | Grammar has no batch (always the grammar batch). | ⚙ Matches the curriculum model; revisit only if grammar ever needs sub-batches. |

---
## Slice 40 — Level-switcher dropdown (by request) (2026-08-10)

**The problem.** Getting to a level's lesson page meant going to `/levels`, tapping a card open,
and clicking "open lessons →" inside it — three steps, and no way to jump directly from one
level's page to another without backing out to the index first.

**`LevelSwitcher`** (new `components/level-switcher.tsx`): a dropdown trigger — "jump to a level",
or "level N" when it knows which level it's on — that opens a grid of number-icon buttons, one per
level. Unlocked levels link straight to `/levels/{n}`; locked ones render as a dimmed, disabled,
non-clickable span with a "— locked" tooltip, the same lock treatment `/levels` already used
elsewhere (never colour alone). Fetches `learn.levels()` itself, so it drops into any page with no
props beyond an optional `current` (which also underlines/borders that level's icon and swaps the
trigger label to show it).

**Placed at the top of the three levels-section pages**: `/levels`, `/levels/[level]`, and
`/levels/[level]/progress`. Deliberately **not** on the active lesson-taking page
(`/levels/[level]/lessons/[lesson]`) — that's a focused task flow, not a browsing page, and jumping
levels mid-lesson isn't something to make one click away.

**By request, this replaces one existing path, not two.** `/levels`' expandable cards (tap to
preview a level's words/grammar in place) stay exactly as they were — that's still how you browse
curriculum. Only the "open lessons →" link inside the expanded card is gone; entering a level's
lesson page is the switcher's job now. "full progress →" is untouched.

**No migration, no backend change.** Reuses the existing `GET /api/v1/levels` the index page
already called.

**Tests:** none added — no new pure logic. Verified live in a headless browser: dropdown opens and
lists all levels with correct lock state, clicking an unlocked level navigates to its page with no
console errors, the trigger shows "level 1" and highlights it when already on `/levels/1`, and
both target texts ("open lessons"/confirmed absent, "full progress"/confirmed present once a card
is expanded) are correct.

**Follow-up, same day (by request): the header nav's "levels" link is the switcher now.**
`LevelSwitcher` gained two optional props — `label` and `triggerClassName` — so the same component
can render as a plain nav-style link instead of its default filled-pill trigger. `components/header.tsx`
swaps the old `<Link href="/levels">` for `<LevelSwitcher label="levels" triggerClassName="...">`,
wrapped in the same `data-tour="nav-levels"` div the guided tour already targeted (no tour changes
needed). Clicking "levels" in the header now opens the dropdown from *any* page instead of
navigating to `/levels` first — confirmed live: the URL doesn't change on click, the panel renders
correctly positioned regardless of which page it's opened from, and picking a level still navigates
correctly. `/levels` itself is unchanged and still reachable (its own in-page switcher, and the
"← levels" back links on the detail/progress pages).

---
## Slice 40 — Level page shows grammar & vocabulary cards (§20, by request) (2026-08-11)

The `/levels/[level]` page listed **lessons** (lesson 1–4 with start/review). By request — and to
match §20 ("displays all vocabulary and grammar for that level; clicking an item shows all
information about it") — it now shows the level's actual curriculum: a **grammar** section of cards
followed by a **vocabulary** section of cards, each card linking to that item's page
(`/items/{type}/{id}`, which already exists).

**Frontend-only.** Swapped the data source from `learn.lessons(level)` to the existing
`items.levelProgress(level)` (`GET /api/v1/levels/{level}/progress`) — the same endpoint the
`/levels` inline expansion already uses — and rendered its `items` split by `item_type` into two
card grids (grammar first, then vocabulary). Each card shows the term (with the article prefix for
nouns), translation, part of speech, and a status pill (perfect ✦ / SRS stage / "not started") — not
colour alone (§29), with hover-lift, keyboard focus rings, and `motion-reduce` fallbacks. All four
states kept: loading, empty, error, populated. The lessons themselves are still reachable from
`/levels` ("open lessons") and remain unchanged.

No API, schema, or migration changes.

**Verified.** The rewritten page and its component test transpile through esbuild; the install
replaces the page (backing up the old one) and is idempotent.

**Tests: frontend +4** (`levels/[level]/__tests__/level-page.test.tsx`): loading state; grammar-then-
vocabulary card order with correct `/items/...` links and the article shown; empty state; error
state. Runs in CI (jest/RTL).

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-111 | The old lesson list moved off this page. | ⚙ Lessons still open from /levels ("open lessons") and each item page; if you want a "start lessons" button on the level page too, easy to add back. |
| R-112 | Card status uses the SRS stage name / "not started" / "perfect". | ⚙ Swap in the richer `progress-bits` pills (SrsPill/LeechPill) if you want the fuller progress affordances here. |

---
## Slice 41 — Header polish + level-page tints (by request) (2026-08-11)

Three requested changes.

**1. Language switcher: flags + "coming soon" for empty languages.**
- The trigger now shows just the **flag** of the active language (globe fallback), with the full
  name kept as an `aria-label` + `sr-only` text and a `title` (§29 — never a flag alone for AT).
- Languages that are enabled but have **no published curriculum** (e.g. Tagalog) are **greyed out**,
  can't be selected, and show a **"coming soon"** tooltip on hover/focus. Readiness is data-driven,
  not hardcoded: a new `ready` flag on `GET /api/v1/languages` (backend), computed by
  `languages.ready_codes(db)` = languages with ≥1 published, non-deleted vocab or grammar item.
  `LanguageOut.ready` defaults `true` so `/me/language` is unaffected. `flagFor(code)` maps known
  codes (es-MX→🇲🇽, tl→🇵🇭, …) and otherwise derives the flag from the region subtag.

**2. Account menu dismisses properly.** The header profile dropdown only closed by re-clicking the
avatar; it now also closes on an **outside click** or **Escape** (mirrors the switcher's pattern),
while the avatar still toggles it.

**3. Level page tints.** On `/levels/[level]`, grammar cards are tinted **red** and vocabulary cards
**green** (soft `red-500/green-500` washes that work in light/dark), with matching section-heading
colours. Colour is additive — the "GRAMMAR"/"VOCABULARY" headings and card text still distinguish
them, so nothing depends on colour alone (§29).

**Verified.** All frontend files transpile; the patched languages service/route and header compile/
transpile; every patcher is idempotent and aborts-without-writing on divergence. The full install
ran end-to-end.

**Tests: frontend +5** (`flagFor` mapping/region/fallback; switcher shows the active flag with an
accessible name; a not-ready language is `aria-disabled` with a "coming soon" tooltip) +
**backend +1 integration** (`test_languages_ready.py`: enabled-but-empty → `ready:false`; publishing
one item flips it to `true`). Backend integration runs in CI (needs the testcontainers DB).

**No migration, no schema change** (readiness is computed from existing published content).

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-113 | Trigger shows flag only; the dropdown list keeps flag **+ name** for usability. | ⚙ If you want flags-only in the list too, drop the name span — but names help tell similar flags apart. |
| R-114 | Card tints use Tailwind `red-500`/`green-500` washes, not brand tokens. | ⚙ Swap for dedicated `--terraza-grammar` / `--terraza-vocab` tokens if you want them themeable. |
| R-115 | Flag map covers the current + likely-next languages; unknown codes fall back to region → globe. | ⚙ Extend `flagFor` as languages are added. |

---
## Slice 42 — Profile tabs + settings sidebar (by request) (2026-08-12)

Two frontend restructures; no API, schema, or migration changes.

**Profile → tabs.** `/profile` now has a tab bar: **profile** (the existing name/bio/timezone editor
+ read-only xp/rank/streak stats), **achievements**, and a right-aligned **＋ add friends** icon that
opens a friends panel. Achievements and friends aren't built (§18 community is future work), so those
tabs show honest **"coming soon"** states — no fabricated badges or friend data. Tabs use
`role="tab"`/`aria-selected` and are keyboard-operable; the add-friends control has an `aria-label`.

**Settings → left sidebar.** `/settings` becomes a two-column layout: a sticky left nav of categories
— **lessons · reviews · appearance · curriculum · intermissions · danger zone** — and a right pane
showing the active one. On mobile the sidebar collapses to a horizontal scroll row. Every setting the
old single-column page surfaced is preserved and redistributed sensibly:
- lessons: batch size.
- reviews: order, batch toggle + size, srs indicator, leech threshold, **+ an "answering" group**
  (reveal full answer, allow cheating, accept synonyms, allow skipping, undo).
- appearance: theme, font size, color theme, **+ immersion mode** (level-10 gated).
- curriculum: mode, back-to-back + order, dialect.
- intermissions: the show-intermissions toggle + a link to view finished intermissions.
- **danger zone** (new): a real **log out** (via `useAuth`), and a **delete account** control that
  is honestly a placeholder — deletion isn't wired yet, so it points the user to the support page
  rather than pretending to delete.

Auto-save, per-field "saved ✓", optimistic update with revert-on-error, and per-field error messages
are kept from the original page.

**Verified.** Both pages and their tests transpile through esbuild; the installer backs up and
replaces the two pages and is idempotent.

**Tests: frontend +6** (`profile-page.test.tsx`: default profile tab with editable name + stats,
achievements coming-soon, add-friends panel; `settings-page.test.tsx`: all six sidebar categories
present, defaults to lessons, switches panels, danger-zone log-out + delete controls). Runs in CI.

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-116 | Achievements + friends are placeholders. | ⚙ Build achievements (badges off streaks/levels/perfect items) and the friends/community layer (§18) in their own slices; the tabs are ready. |
| R-117 | "answering" toggles fold under **reviews** (not a top-level sidebar item, per the requested six). | ⚙ Split "answering" into its own sidebar category if you'd rather; it's a one-line add. |
| R-118 | Delete-account is a placeholder pointing to support. | ⚙ Wire a real `DELETE /me/account` (soft-delete + grace period + re-auth confirm) when account deletion is scoped. |

---
## Slice 43 — Deck unlocks + learner-built decks (§15, by request) (2026-08-12)

Decks were three always-on collections (vocabulary/grammar/intermissions). Now the decks page is a
catalog: always-on decks, **threshold-gated decks** that unlock as items reach Familiar, and
**custom decks** the learner creates — with a see-through **"+"** ghost card to make one.

**Unlock logic is pure + tested.** `domain/deck_unlock.py` holds the catalog (`BUILTIN_DECKS`) and
`evaluate(counts) → DeckState[]`. A deck unlocks when a category's Familiar+ count (SRS ≥ 5) meets
its threshold — e.g. **20 verbs → verbs deck**, **5 irregular verbs → irregular-verbs deck**. Category
keys: `pos:<pos>` and `regularity:{regular,irregular}`. Shipped catalog also includes regular verbs
(15), nouns (30), adjectives (15), adverbs (10). Fully unit-tested (thresholds, progress, isolation).

**Backend.** `services/deck_catalog.py` computes `familiar_counts` (Familiar+ vocab by pos + verb
regularity via `VerbMeta`), merges the always-on decks' live counts, and lists custom decks. Custom
decks persist in a new **`custom_decks`** table (id, user_id, name, description, item_refs JSON,
timestamps, soft-delete) — migration generated at install time chained to the real Alembic head
(same head-computation approach as slice 39; aborts if not exactly one head). Routes appended to the
decks router under multi-segment paths so they never collide with `GET /me/decks/{deck_type}`:
`GET /me/decks/catalog/all`, `POST /me/decks/catalog/custom`, `DELETE /me/decks/catalog/custom/{id}`.

**Frontend.** `/decks` renders the catalog: unlocked decks show their glyph + count; **locked decks
are greyed with a 🔒, a "have/threshold familiar · N to go" line, and a progress bar** (not colour
alone, §29); custom decks show a remove link; and a dashed **"+" ghost card** opens a create modal
(name + description → `POST` → refresh). Always-on decks link to their item list as before; browsing
the *contents* of unlockable/custom decks is the next slice.

**Verified.** Pure logic runs green; the appended routes, the service, the `CustomDeck` model block,
the generated migration, and both test files `py_compile`; the migration generator was exercised on
a fake versions tree (chains to head, idempotent, aborts on multiple heads); the decks page + client
transpile. Installer is idempotent and aborts-without-writing on divergence.

**Tests: backend +14** (`test_deck_unlock.py` pure, runnable now; `test_deck_catalog_db.py`
integration: catalog states, irregular-deck unlock at 5 + verbs progress, custom create/list/delete,
name required, can't delete another user's deck, auth required — runs in CI).

**Requested outline** of deck-unlock ideas: `docs/DECK_UNLOCKS.md` (pos decks, verb-class decks,
tag/theme decks, level-milestone decks, leech/perfect/due-today, difficulty tiers) + how to add one.

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-119 | Browsing the *items inside* unlockable/custom decks isn't wired yet (always-on decks work). | ⚙ Next slice: `GET /me/decks/catalog/{id}/items` (pos/regularity filter for builtin; item_refs for custom) + a catalog deck detail page. |
| R-120 | Custom decks are created empty; no item-picker yet. | ⚙ Add "add to deck" from item pages (writes item_refs); the table already stores them. |
| R-121 | Counts use es-MX (matching the existing decks service), not the active language. | ⚙ Thread active language through decks when R-65 is done. |
| R-122 | Thresholds (20 verbs, 5 irregular, …) are filler constants. | ⚙ Tune in `deck_unlock.py`; they're named per deck. |

---
## Slice 44 — Item page redesign + per-item notes (by request) (2026-08-13)

Reworked `/items/[type]/[id]` to the requested layout, and added a couple of small backends the
design needs. Content width is now `max-w-4xl` (wider, not full-bleed), section headings are larger,
and the section spacing is fixed (`gap-8`), which removes the "your synonyms" overlap.

**New layout, top → bottom**
- **Hero, no card:** big centered term + translation + audio + status. When it scrolls out of view an
  IntersectionObserver reveals a **sticky sub-header** (term · translation · SRS) below the app header.
- **Pronunciation box** (pronunciation, IPA, play button) | **synonyms & variants** (curriculum
  synonyms + variants, plus the learner's own synonyms with add/remove).
- **meaning** (dictionary definition) · **curriculum notes** (admin-authored: grammar explanation/
  structure today; a dedicated vocab field is a later slice) · **your notes** (editable textarea with a
  live word count, ≤250 words, and clear / save buttons bottom-right).
- **context phrases** — WaniKani-style tabs on the left, phrases on the right. The `context` JSON shape
  isn't fixed, so a defensive normaliser accepts several key spellings and shows an empty state when
  there's nothing.
- **examples** — sentence + translation + audio.
- **your progress** (SRS pill + "<time> until next review") | **practice stages** (Uno–Cinco dots per
  category).
- **item stats** — meaning / reading / combined accuracy (derived from review history by prompt
  direction), plus unlock and retiring dates.

**Review-time rounding** (`timeUntilReview`, pure + tested): month → week → day → hour → "less than an
hour", then exact minutes in the last five ("4 minutes until next review"); "review available now" when
due. Verified against all boundaries.

**Backend — per-item notes.** New `user_item_notes` table (unique per user+item; migration generated at
install time, chained to the real Alembic head, aborts on multiple heads). `UserItemNote` model appended
to `progress.py`. `GET/PUT /api/v1/items/{type}/{id}/note` on the items router, scoped per user and
level-gated like every other item read. The 250-word cap is a pure validator (`domain/notes.py`),
enforced server-side (422 over the limit) and mirrored in the UI's live counter.

**Item stats need no new backend** — meaning (es_to_en) vs reading (en_to_es) accuracy is computed on the
client from the existing history endpoint; unlock/retire dates come from `progress`.

**Verified.** Pure notes validator + the review-time formatter run green (all boundaries); the migration,
the `UserItemNote` model block, the service block, the route block, and both backend test files
`py_compile`; the migration generator chains to head, is idempotent, and aborts on multiple heads; the
item page + helpers transpile. Installer is idempotent and aborts-without-writing on divergence.

**Tests: backend +10** (`test_notes.py` pure; `test_item_notes_db.py` integration: empty→save→reload,
clear, 250-word rejection, auth required, per-user isolation) **+ frontend** (`item-extras.test.ts`:
time rounding across every bucket, word count, date format). Backend integration runs in CI.

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-123 | "Curriculum notes" reuses grammar explanation/structure; vocab has no dedicated admin-notes field. | ⚙ Add a `curriculum_notes` column + admin editor field in a later slice; the card is ready. |
| R-124 | Context tabs parse a best-guess JSON shape (several key spellings) and empty-state otherwise. | ⚙ Pin the `context` schema, then the normaliser can be tightened; seed data can populate it. |
| R-125 | Item stats read the last 100 review answers (history cap). | ⚙ Fine for now; add a server-side by-direction aggregate if very active items need exact lifetime totals. |
| R-126 | "Retiring date" = `fluent_at` (when it retires to Fluent), else "not yet". | ⚙ Swap for a projected burn date if you'd rather show a forecast. |
| R-127 | Sticky sub-header uses `top-0`. | ⚙ If the app header is sticky in your build, offset it by the header height. |

---
## Slice 45 — Spring animations in onboarding (Motion) (2026-08-13)

First use of spring animation in the app (§35). Added **Motion** (formerly Framer Motion,
`"motion": "^12.0.0"`, imported from `motion/react`) and reworked `apps/web/app/welcome/page.tsx`.
The existing `SlideArt` SVGs and `NotebookGag` are untouched — this is a surgical patch, not a rewrite.

**Per-slide spring animation.** Each slide is a keyed `motion.div` inside `AnimatePresence` (`mode="wait"`):
the panel springs in from the swipe direction and out the other way, and its contents (art, title, body,
gag) **stagger in** with a gentle spring via variants (`staggerChildren`). Direction is tracked so back
and next animate opposite ways. Two spring "personalities" — a smooth slide for the panel, a softer pop
for contents. `useReducedMotion()` collapses everything to instant + opacity (§29).

**Sticky footer (buttons stop moving).** The layout changed from one vertically-centered stack to a
column: the slide lives in a `flex-1` animation area (centered within), and the **back/next bar sits in a
fixed footer**, so it stays in the same place on every slide instead of shifting with slide height.

**Dots moved below the animation.** The progress dots were above the art; they're now in the footer,
below the animation and above the buttons, and the active dot springs its width. A visually-hidden
`aria-live` "step N of 5" rides alongside for screen readers.

**Verified.** Both patchers apply to a faithful skeleton, transpile through esbuild, and are idempotent
(abort-without-writing on divergence); the package.json insert keeps valid JSON; the component test
transpiles. Motion's runtime API (`motion`, `AnimatePresence`, `useReducedMotion`, variants, spring
transitions) is standard and documented, but note it isn't executed in the sandbox — it runs after
`npm install` on rebuild.

**Tests: frontend +4** (`welcome/__tests__/onboarding.test.tsx`, Motion mocked): first slide + skip/next,
advance shows back, "step 1 of 5" announcement renders below the slide, last slide finishes to
`/choose-language`. Runs in CI.

**Requires `npm install`** (new dependency) — a `docker compose up --build` does this automatically.

### Open questions

| # | Item | Filler decision (changeable) |
|---|---|---|
| R-128 | Motion variants use `type: "spring"` string literals typed via `Variants`. | ⚙ If `next build`'s strict TS ever rejects a literal, it's a one-line `as const` on that transition. |
| R-129 | Spring constants (stiffness/damping) are inline. | ⚙ Promote to shared `springs.ts` tokens when Motion spreads to reviews/dashboard (next animation slices). |
| R-130 | SlideArt internals aren't individually spring-animated yet (whole art pops in). | ⚙ Can stagger the SVG shapes (stepping stones, trail signs) per slide later for extra life. |
