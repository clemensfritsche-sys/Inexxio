import { useEffect, useRef, useState, useCallback } from 'react';

export type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error';

export function useAutosave<T>(
  value: T,
  save: (v: T) => Promise<void>,
  delay = 3000,
  resetKey?: unknown,
): { status: SaveStatus; errorMsg: string; saveNow: () => Promise<void> } {
  const [status, setStatus] = useState<SaveStatus>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const skipRef = useRef(true);
  const saveRef = useRef(save);
  saveRef.current = save;
  const valueRef = useRef(value);
  valueRef.current = value;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    skipRef.current = true;
  }, [resetKey]);

  useEffect(() => {
    if (skipRef.current) {
      skipRef.current = false;
      return;
    }
    setStatus('dirty');
    timerRef.current = setTimeout(async () => {
      setStatus('saving');
      try {
        await saveRef.current(value);
        setStatus('saved');
        timerRef.current = setTimeout(() => setStatus('idle'), 2500);
      } catch (e: unknown) {
        setErrorMsg(e instanceof Error ? e.message : 'Fehler');
        setStatus('error');
      }
    }, delay);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value, delay]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveNow = useCallback(async () => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    setStatus('saving');
    try {
      await saveRef.current(valueRef.current);
      setStatus('saved');
      timerRef.current = setTimeout(() => setStatus('idle'), 2500);
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Fehler');
      setStatus('error');
    }
  }, []);

  return { status, errorMsg, saveNow };
}
