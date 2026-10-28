'use client';

/** Verfassen im Chat – folgt in Stufe 4. */
export function ComposeChat({ onDone }: {
  onDone: (files: Blob[], art: string, name: string, refs: { object_id: number; label: string }[]) => void;
}) {
  void onDone;
  return null;
}
