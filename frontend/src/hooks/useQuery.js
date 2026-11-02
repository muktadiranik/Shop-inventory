import { useCallback, useEffect, useState } from 'react';
import { graphqlRequest } from '../api/client.js';

export default function useQuery(query, variables = {}) {
  const key = JSON.stringify(variables);
  const [version, setVersion] = useState(0);
  const [state, setState] = useState({ query, key, version, data: null, loading: true, error: null });
  const refetch = useCallback(() => setVersion((value) => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    const request = { query, key, version };
    setState({ ...request, data: null, loading: true, error: null });
    graphqlRequest(query, JSON.parse(key), { signal: controller.signal }).then(
      (data) => { if (!controller.signal.aborted) setState({ ...request, data, loading: false, error: null }); },
      (error) => { if (!controller.signal.aborted) setState({ ...request, data: null, loading: false, error }); },
    );
    return () => controller.abort();
  }, [query, key, version]);
  // Effects run after rendering. Never expose a previous filter/page's data in
  // that intermediate render: consumers could act on an obsolete total count.
  const current = state.query === query && state.key === key && state.version === version
    ? state : { data: null, loading: true, error: null };
  return { data: current.data, loading: current.loading, error: current.error, refetch };
}
