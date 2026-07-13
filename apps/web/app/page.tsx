/**
 * Placeholder shell (slice 1a). Real dashboard lands in slice 1d,
 * auth in 1c. No fake data beyond this clearly-marked placeholder.
 */
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-6 p-8 text-center">
      <span className="rounded-full bg-terraza-pill px-4 py-2 text-sm tracking-label">
        POLYGLOT · TERRAZA
      </span>
      <h1 className="text-4xl lowercase tracking-cozy">
        hola <span className="text-terraza-accent">✦</span>
      </h1>
      <p className="max-w-md text-terraza-soft">
        the scaffold is alive. auth, dashboard, and lessons arrive in the next slices.
      </p>
      <p className="font-empty italic text-terraza-soft">nothing here yet ~</p>
    </main>
  );
}
