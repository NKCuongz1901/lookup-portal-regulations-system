"use client";
import { useCallback, useEffect, useState } from "react";
import { requestError } from "@/ultis/requestError";

export default function useResource<T>(loader: (signal: AbortSignal) => Promise<T>) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ loader: typeof loader; revision: number; data: T | null; error: string | null } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.resolve().then(() => loader(controller.signal)).then((data) => {
      if (!controller.signal.aborted) setResult({ loader, revision, data, error: null });
    }).catch((error) => {
      if (!controller.signal.aborted) setResult({ loader, revision, data: null, error: requestError(error) });
    });
    return () => controller.abort();
  }, [loader, revision]);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  const loading = result?.loader !== loader || result?.revision !== revision;
  return { data: result?.data ?? null, loading, error: loading ? null : result?.error ?? null, reload };
}
