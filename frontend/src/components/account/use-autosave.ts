import { useEffect, useRef, useState } from 'react';

export type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error';

export function useAutosave<T>(
  value: T,
  save: (v: T) => Promise<void>,
  delay = 3000,
  resetKey?: unknown,
): { status: SaveStatus; errorMsg: string } {
  const [status, setStatus] = useState<SaveStatus>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const skipRef = useRef(true);
  const saveRef = useRef(save);
  saveRef.current = save;

  // When resetKey changes, mark next value change as initialization (skip save)
  useEffect(() => {
    skipRef.current = true;
  }, [resetKey]);

  useEffect(() => {
    if (skipRef.current) {
      skipRef.current = false;
      return;
    }
    setStatus('dirty');
    const timer = setTimeout(async () => {
      setStatus('saving');
      try {
        await saveRef.current(value);
        setStatus('saved');
        const t = setTimeout(() => setStatus('idle'), 2500);
        return () => clearTimeout(t);
      } catch (e: unknown) {
        setErrorMsg(e instanceof Error ? e.message : 'Fehler');
        setStatus('error');
      }
    }, delay);
    return () => clearTimeout(timer);
  }, [value, delay]); // eslint-disable-line react-hooks/exhaustive-deps

  return { status, errorMsg };
}
