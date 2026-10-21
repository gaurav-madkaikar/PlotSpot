import { z } from 'zod'

export const movieSchema = z.object({
  id: z.number().int().positive(),
  title: z.string(),
  detail_metadata: z
    .object({
      version: z.literal(1),
      release_date: z.string().nullable(),
      spoken_languages: z.array(z.string()),
      production_companies: z.array(z.string()),
      production_countries: z.array(z.string()),
      budget: z.number().int().nonnegative().nullable(),
      revenue: z.number().int().nonnegative().nullable(),
      vote_average: z.number().min(0).max(10).nullable(),
      vote_count: z.number().int().nonnegative().nullable(),
      status: z.string().nullable(),
      original_title: z.string().nullable(),
      cast_credits: z
        .array(
          z.object({
            name: z.string(),
            character: z.string().nullable(),
            profile_url: z
              .string()
              .regex(
                /^https:\/\/image\.tmdb\.org\/t\/p\/w185\/[A-Za-z0-9_-]+\.(?:jpg|png|webp)$/,
              )
              .nullable(),
          }),
        )
        .max(12),
      presentation_version: z.literal(1).nullable().optional(),
      creative_credits: z
        .array(
          z.object({
            name: z.string().min(1).max(200),
            role: z.enum([
              'Writer',
              'Screenplay',
              'Story',
              'Composer',
              'Cinematographer',
            ]),
          }),
        )
        .max(20)
        .default([]),
      trailer: z
        .object({
          name: z.string().min(1).max(200),
          youtube_key: z.string().regex(/^[A-Za-z0-9_-]{11}$/),
          official: z.boolean(),
        })
        .nullable()
        .optional(),
    })
    .nullable()
    .optional(),
  vote_average: z.number().min(0).max(10).nullable().optional(),
  vote_count: z.number().int().nonnegative().nullable().optional(),
  adult: z.boolean().nullable().optional(),
  year: z.number().int().nullable(),
  runtime_minutes: z.number().int().positive().nullable(),
  language: z.string(),
  genres: z.array(z.string()),
  director: z.string().nullable(),
  cast: z.array(z.string()),
  overview: z.string(),
  tagline: z.string(),
  cover_url: z
    .string()
    .regex(
      /^(?:\/covers\/[0-9]+\.svg|https:\/\/image\.tmdb\.org\/t\/p\/w500\/[A-Za-z0-9_-]+\.(?:jpg|png|webp))$/,
    )
    .nullable(),
  source: z.enum(['demo', 'tmdb']),
  artwork_kind: z.enum(['illustration', 'poster', 'placeholder']),
})

export const personNameSchema = z.object({
  id: z.number().int().positive(),
  name: z.string().min(1),
  adult: z.boolean().nullable().optional(),
  known_for_department: z.string().nullable(),
  known_for_titles: z.array(z.string()).max(5).default([]),
})

export const movieSearchSchema = z.object({
  items: z.array(movieSchema),
  total: z.number().int().nonnegative(),
  data_source: z.enum(['demo', 'tmdb']),
  limited: z.boolean().default(false),
  page: z.number().int().positive().default(1),
  page_size: z.number().int().min(1).max(40).default(20),
  total_pages: z.number().int().nonnegative().default(1),
  indexed_movies: z.number().int().nonnegative().nullable().optional(),
  match_type: z
    .enum(['browse', 'title_cast', 'typo', 'genre', 'keyword'])
    .default('title_cast'),
  applied_genres: z.array(z.string()).max(20).default([]),
  matched_query: z.string().nullable().optional(),
  partial: z.boolean().default(false),
  people: z.array(personNameSchema).max(20).default([]),
  selected_person: personNameSchema.nullable().default(null),
  person_role: z.enum(['actor', 'director']).nullable().default(null),
  search_token: z
    .string()
    .regex(/^[a-f0-9]{32}$/)
    .nullable()
    .default(null),
  snapshot_reset: z.boolean().default(false),
})

export const healthSchema = z.object({
  status: z.string(),
  data_source: z.enum(['demo', 'tmdb']),
})

export const suggestionSchema = z.object({
  items: z.array(
    z.object({
      label: z.string(),
      kind: z.enum(['movie', 'actor', 'director']),
      movie_ids: z.array(z.number().int().positive()),
      score: z.number().min(0).max(1),
    }),
  ),
  indexed_movies: z.number().int().nonnegative(),
  limited: z.literal(true),
})

export type Movie = z.infer<typeof movieSchema>

export const scriptContextSchema = z.object({
  source_ref: z
    .string()
    .regex(/^https:\/\/imsdb\.com\/scripts\/[^/?#]+\.html$/),
  version: z.string().max(120),
  released_film_verified: z.literal(false),
})

export const movieAnswerSchema = z.object({
  status: z.enum([
    'answered',
    'insufficient_evidence',
    'source_unavailable',
    'spoiler_permission_required',
  ]),
  answer: z.string().max(4000),
  source_coverage: z
    .object({
      degraded: z.boolean(),
      source_count: z.number().int().nonnegative(),
    })
    .passthrough()
    .nullable()
    .optional(),
  answer_kind: z.enum(['event', 'interpretation']).default('event'),
  script_context: scriptContextSchema.nullable().default(null),
  citations: z
    .array(
      z
        .object({
          passage_id: z.string().max(64),
          source_label: z.string().max(200),
          source_kind: z.enum(['reviewed', 'web']).default('reviewed'),
          source_verified: z.boolean().default(false),
          source_ref: z.string().max(500),
          revision: z.string().max(100),
          excerpt: z.string().max(600),
        })
        .superRefine((citation, ctx) => {
          const reviewed =
            /^(?:https:\/\/en\.wikipedia\.org\/w\/index\.php\?oldid=[1-9][0-9]*|https:\/\/authors\.library\.caltech\.edu\/records\/awp8p-s4d82|https:\/\/time\.com\/4677598\/arrival-oscar-cinematography\/|https:\/\/www\.bfi\.org\.uk\/features\/strange-new-worlds-craft-denis-villeneuve)$/.test(
              citation.source_ref,
            )
          let acquired = false
          try {
            const url = new URL(citation.source_ref)
            acquired =
              citation.source_kind === 'web' &&
              citation.source_verified &&
              /^web-[a-f0-9]{64}$/.test(citation.revision) &&
              url.protocol === 'https:' &&
              !url.username &&
              !url.password &&
              (!url.port || url.port === '443') &&
              /^[a-z0-9.-]+$/.test(url.hostname) &&
              url.hostname.includes('.') &&
              url.hostname !== 'imsdb.com' &&
              !/^(?:localhost|[0-9.]+)$/.test(url.hostname) &&
              !/\.(?:local|internal|localhost|onion)$/.test(url.hostname)
          } catch {}
          if (!reviewed && !acquired)
            ctx.addIssue({ code: 'custom', message: 'Unverified source URL' })
        }),
    )
    .max(3),
})

export type MovieAnswer = z.infer<typeof movieAnswerSchema>

export const movieQuizSchema = z.object({
  can_generate_more: z.boolean().default(true),
  prepared_at: z.string().nullable().optional(),
  content_version: z.string().nullable().optional(),
  status: z.enum([
    'ready',
    'source_unavailable',
    'spoiler_permission_required',
  ]),
  message: z.string(),
  items: z
    .array(
      z.object({
        origin: z.enum(['reviewed', 'generated']).default('reviewed'),
        id: z.string(),
        question: z.string(),
        kind: z.enum(['plot', 'ending', 'interpretation']).default('plot'),
        options: z.array(z.string()).length(4),
        correct_index: z.number().int().min(0).max(3),
        explanation: z.string().max(4000),
        citations: movieAnswerSchema.shape.citations.min(1),
      }),
    )
    .max(40),
})
export type MovieQuiz = z.infer<typeof movieQuizSchema>

export const movieFactsSchema = z.object({
  reading_sources: z
    .array(
      z.object({
        kind: z.enum(['research', 'early_draft', 'interview', 'article']),
        title: z.string().max(200),
        source_ref: z
          .string()
          .regex(
            /^https:\/\/(?:authors\.library\.caltech\.edu\/records\/awp8p-s4d82|imsdb\.com\/scripts\/Interstellar\.html|time\.com\/4677598\/arrival-oscar-cinematography\/|www\.bfi\.org\.uk\/features\/strange-new-worlds-craft-denis-villeneuve)$/,
          ),
        publisher: z.string().max(100),
        date: z.string().max(20),
        authors: z.array(z.string()).max(20),
        note: z.string().max(250),
        retrieved_at: z.string().max(40),
        content_sha256: z.string().regex(/^[a-f0-9]{64}$/),
      }),
    )
    .max(4)
    .default([]),
  prepared_at: z.string().nullable().optional(),
  content_version: z.string().nullable().optional(),
  status: z.enum([
    'ready',
    'source_unavailable',
    'spoiler_permission_required',
  ]),
  message: z.string(),
  items: z
    .array(
      z.object({
        id: z.string(),
        title: z.string(),
        text: z.string().max(4000),
        citations: movieAnswerSchema.shape.citations.min(1),
      }),
    )
    .max(12),
})
export type MovieFacts = z.infer<typeof movieFactsSchema>

export const movieFeaturesSchema = z.object({
  movie_id: z.number().int().positive(),
  discussion: z.boolean(),
  quiz: z.boolean(),
  facts: z.boolean(),
})

export const nameSearchSchema = z.object({
  items: z.array(movieSchema).max(20),
  people: z.array(personNameSchema).max(20),
  selected_person: personNameSchema.nullable(),
  role: z.enum(['actor', 'director']),
  page: z.number().int().min(1).max(100),
  has_more: z.boolean(),
  partial: z.boolean(),
  limited: z.boolean(),
})

export const watchRegionsSchema = z.object({
  items: z
    .array(
      z.object({
        code: z.string().regex(/^[A-Z]{2}$/),
        name: z.string().min(1).max(100),
      }),
    )
    .max(300),
  checked_at: z.string().datetime({ offset: true }).nullable(),
  stale: z.boolean(),
})
export const watchOptionsSchema = z
  .object({
    movie_id: z.number().int().positive(),
    country: z.string().regex(/^[A-Z]{2}$/),
    status: z.enum(['available', 'unavailable', 'source_unavailable']),
    groups: z
      .array(
        z.object({
          kind: z.enum(['subscription', 'free', 'ads', 'rent', 'buy']),
          providers: z
            .array(
              z.object({
                id: z.number().int().positive(),
                name: z.string().min(1).max(200),
                logo_url: z
                  .string()
                  .regex(
                    /^https:\/\/image\.tmdb\.org\/t\/p\/w92\/[A-Za-z0-9_-]+\.(?:jpg|png|webp)$/,
                  )
                  .nullable(),
              }),
            )
            .max(40),
        }),
      )
      .max(5),
    watch_url: z
      .string()
      .regex(
        /^https:\/\/www\.themoviedb\.org\/movie\/[1-9][0-9]*(?:-[^/?#]+)?\/watch\?locale=[A-Z]{2}$/,
      )
      .nullable(),
    checked_at: z.string().datetime({ offset: true }).nullable(),
    stale: z.boolean(),
  })
  .refine(
    (value) =>
      !value.watch_url ||
      (new URL(value.watch_url).pathname.match(/^\/movie\/([0-9]+)/)?.[1] ===
        String(value.movie_id) &&
        new URL(value.watch_url).searchParams.get('locale') === value.country),
  )
export const relatedMoviesSchema = z.object({
  movie_id: z.number().int().positive(),
  checked_at: z.string().datetime({ offset: true }).nullable(),
  stale: z.boolean(),
  items: z
    .array(
      z.object({
        id: z.number().int().positive(),
        title: z.string().min(1).max(200),
        year: z.number().int().min(1888).max(2100).nullable(),
        adult: z.boolean().nullable(),
        vote_average: z.number().min(0).max(10).nullable().optional(),
        vote_count: z.number().int().nonnegative().nullable().optional(),
        poster_url: z
          .string()
          .regex(
            /^https:\/\/image\.tmdb\.org\/t\/p\/w500\/[A-Za-z0-9_-]+\.(?:jpg|png|webp)$/,
          )
          .nullable(),
      }),
    )
    .max(6),
})
export type RelatedMovie = z.infer<typeof relatedMoviesSchema>['items'][number]

export const draftStatusSchema = z.object({
  available: z.boolean(),
  job: z
    .object({
      id: z.string().regex(/^[a-f0-9]{32}$/),
      movie_id: z.number().int().positive(),
      state: z.enum([
        'queued',
        'running',
        'needs_review',
        'incomplete',
        'failed',
        'cancelled',
        'interrupted',
        'ready',
        'published',
      ]),
      phase: z.enum([
        'source',
        'retrieving',
        'generating',
        'reviewing',
        'finished',
      ]),
      updated_at: z.string().datetime({ offset: true }),
      message: z.string().max(250),
      facts_retained: z.number().int().min(0).max(5),
      questions_retained: z.number().int().min(0).max(10),
      batches_completed: z.number().int().min(0).max(8),
      publication_approved: z.boolean(),
      refresh: z.boolean().default(false),
      items: z
        .array(
          z.object({
            id: z.string().max(30),
            kind: z.enum(['fact', 'question']),
            title: z.string().max(250),
            text: z.string().max(450),
            options: z.array(z.string().max(150)).max(4),
            correct_index: z.number().int().min(0).max(3).nullable(),
            decision: z.enum(['accept', 'reject', 'uncertain']),
            retained: z.boolean(),
            reason: z.string().max(400),
            evidence_quote: z.string().max(600),
            origin: z
              .object({
                movie_id: z.number().int().positive(),
                source_id: z.string().max(64),
                source_ref: z.string().max(500),
                revision: z.string().max(100),
                section_title: z.string().max(200),
                section_category: z.enum([
                  'plot',
                  'production',
                  'casting',
                  'filming',
                  'music',
                  'effects',
                  'other',
                ]),
                start: z.number().int().nonnegative(),
                end: z.number().int().positive(),
              })
              .refine(
                (origin) =>
                  movieAnswerSchema.shape.citations.element.safeParse({
                    passage_id: 'origin',
                    source_label: 'Retained source',
                    source_ref: origin.source_ref,
                    revision: origin.revision,
                    excerpt: 'Retained evidence origin',
                    source_kind: 'web',
                    source_verified: true,
                  }).success,
                'Invalid retained source reference',
              ),
          }),
        )
        .max(48),
    })
    .nullable(),
})
export type DraftStatus = z.infer<typeof draftStatusSchema>
