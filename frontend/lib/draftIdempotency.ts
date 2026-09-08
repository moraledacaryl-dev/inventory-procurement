export type DraftIdempotencyState = {
  signature: string;
  key: string;
};

export function stableDraftIdempotency(
  draft: unknown,
  previous: DraftIdempotencyState | null,
  makeKey: () => string = () => crypto.randomUUID(),
): DraftIdempotencyState {
  const signature = JSON.stringify(draft);
  if (previous?.signature === signature) {
    return previous;
  }
  return { signature, key: makeKey() };
}
