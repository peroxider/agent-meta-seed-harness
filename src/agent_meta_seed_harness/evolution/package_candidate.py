"""Consumer-side package-candidate construction (S09) over public SDK contracts only.

A code candidate is a full new AMPAK package version that must pass the same
release gates as any human release — no fast lane exists. The candidate tree
is physically isolated (built from explicit copied bytes, never mutating the
live sources), the builder refuses to mint two different candidate trees
under one identity without advancing the descriptor revision, the per-day
candidate budget is bounded by a frozen ceiling the agent cannot raise, and
every stage is explicit: failures exit and are never retried or scheduled —
there is no resident evolution loop.
"""
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

CODE_BUDGET_CEILING = {'max_candidates_per_day': 1, 'max_generation_tokens': 200_000,
    'max_experiment_wall_time_us': 600_000_000}


class CodeCandidateError(Exception):
    """Fail-closed exit: the candidate cannot be built under S09 governance."""


def build_candidate_tree(base_sources, overrides, *, version, descriptor_revision, previous):
    """Return an isolated candidate source tree; the base is never mutated.

    ``previous`` carries the identity of the already-generated candidate, if
    any: the same package version with different content is refused — the
    descriptor revision must advance instead.
    """
    if previous is not None and previous['version'] == version and previous['content_sha256'] != sha256_hex(canonical_json(
            {'sources': {path: sha256_hex(raw) for path, raw in sorted({**base_sources, **overrides}.items())}},
            )) and previous['descriptor_revision'] == descriptor_revision:
        raise CodeCandidateError('same identity with different content requires a descriptor revision advance')
    return {**base_sources, **overrides}


class CandidateBudget:
    def __init__(self, *, max_candidates_per_day, max_generation_tokens, max_experiment_wall_time_us):
        policy = {'max_candidates_per_day': max_candidates_per_day, 'max_generation_tokens': max_generation_tokens,
            'max_experiment_wall_time_us': max_experiment_wall_time_us}
        for key, ceiling in CODE_BUDGET_CEILING.items():
            if policy[key] > ceiling:
                raise CodeCandidateError(f'budget exceeds frozen ceiling: {key}')
        self._policy = policy
        self._per_day = {}

    def register_candidate(self, *, day, generation_tokens):
        if self._per_day.get(day, 0) >= self._policy['max_candidates_per_day']:
            raise CodeCandidateError(f'candidate budget exhausted for day {day}')
        self._per_day[day] = self._per_day.get(day, 0) + 1
        return self._policy['max_candidates_per_day'] - self._per_day[day]
