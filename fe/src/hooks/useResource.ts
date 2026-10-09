"use client";
import { useCallback, useEffect, useState } from "react";
import { requestError } from "@/ultis/requestError";

export default function useResource<T>(loader: (signal: AbortSignal) => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null);
    loader(controller.signal).then((result) => {
      if (!controller.signal.aborted) setData(result);
    }).catch((error) => {
      if (!controller.signal.aborted) { setData(null); setError(requestError(error)); }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [loader, revision]);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  return { data, loading, error, reload };
}
