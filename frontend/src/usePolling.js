import { useCallback, useEffect, useRef, useState } from "react";

// Calls `load` now and then every `intervalMs` while `active` is true.
// `active` can also be a function of the latest data, e.g. stop polling
// once a batch has finished. Returns { data, error, reload }.
export function usePolling(load, intervalMs, active = true) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const loadRef = useRef(load);
  loadRef.current = load;

  const reload = useCallback(async () => {
    try {
      setData(await loadRef.current());
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const isActive = typeof active === "function" ? active(data) : active;

  useEffect(() => {
    if (!isActive) return undefined;
    const timer = setInterval(reload, intervalMs);
    return () => clearInterval(timer);
  }, [isActive, intervalMs, reload]);

  return { data, error, reload };
}
