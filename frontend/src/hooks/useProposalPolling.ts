import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAgentProposal } from '../api/endpoints';
import { ApiRequestError } from '../api/client';

const PROPOSAL_POLL_INTERVAL = 3_000;
const PROPOSAL_POLL_LIMIT = 120_000;

export function useProposalPolling(
  jobId: string | null | undefined,
  token: string | null,
) {
  const startedAt = useRef(Date.now());
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    startedAt.current = Date.now();
    setElapsedSeconds(0);

    if (!jobId) return;

    const timer = window.setInterval(() => {
      setElapsedSeconds(
        Math.floor((Date.now() - startedAt.current) / 1_000),
      );
    }, 1_000);

    return () => window.clearInterval(timer);
  }, [jobId]);

  const query = useQuery({
    queryKey: ['proposal', jobId],
    queryFn: () => getAgentProposal(jobId!, token!),
    enabled: Boolean(jobId && token),
    retry: false,
    refetchInterval: (currentQuery) => {
      const proposal = currentQuery.state.data;
      if (proposal) {
        return proposal.status === 'pending_approval' ? 15_000 : false;
      }

      const error = currentQuery.state.error;
      if (
        error &&
        !(error instanceof ApiRequestError && error.status === 404)
      ) {
        return false;
      }

      return Date.now() - startedAt.current < PROPOSAL_POLL_LIMIT
        ? PROPOSAL_POLL_INTERVAL
        : false;
    },
  });

  const isNotReady =
    query.error instanceof ApiRequestError && query.error.status === 404;

  return {
    ...query,
    elapsedSeconds,
    isNotReady,
    isTakingLonger:
      elapsedSeconds >= PROPOSAL_POLL_LIMIT / 1_000 &&
      !query.data &&
      (!query.error || isNotReady),
  };
}
