import { useRef, useState } from 'react';

export default function useAction() {
  const locked = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  async function run(action) {
    // The synchronous lock covers clicks before React renders disabled=true.
    if (locked.current) return null;
    locked.current = true;
    setPending(true);
    setError(null);
    try {
      return await action();
    } catch (error) {
      setError(error);
      return null;
    } finally {
      locked.current = false;
      setPending(false);
    }
  }
  return { run, pending, error, clearError: () => setError(null) };
}
