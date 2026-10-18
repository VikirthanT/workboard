/** Full-page placeholder shown until the data a screen needs is ready, so it paints once instead of in pieces. */
export function PageLoading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex min-h-[60vh] items-center justify-center gap-2.5 text-base text-ink-subtle">
      <span aria-hidden className="inline-block size-4 animate-spin rounded-full border-2 border-line-strong border-t-brand" />
      {label}
    </div>
  );
}
