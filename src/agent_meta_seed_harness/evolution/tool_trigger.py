"""Consumer-side bounded Evolution trigger policy (S08) over public SDK contracts only.

Failure history read through public bounded traces drives event-driven
Proposals, but every trigger is bounded: at most one Proposal per window, a
cooldown per target path, and hard caps declared by the policy — attempts to
construct a wider policy than the frozen ceiling are refused, so an agent
cannot raise its own limits. Missing history never triggers; the policy never
fabricates a Proposal from nothing.
"""
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

TRIGGER_CEILING = {'max_proposals_per_window': 1, 'max_candidates_per_window': 2,
    'max_experiments_per_window': 2, 'cooldown_us': 300_000_000}


class TriggerLimitError(Exception):
    """Fail-closed exit: the requested trigger exceeds the declared bounds."""


def policy_digest(policy):
    return sha256_hex(canonical_policy(policy))


def canonical_policy(policy):
    return canonical_json({key: policy[key] for key in sorted(policy)})


class TriggerPolicy:
    def __init__(self, *, max_proposals_per_window, max_candidates_per_window,
                 max_experiments_per_window, cooldown_us):
        policy = {'max_proposals_per_window': max_proposals_per_window,
            'max_candidates_per_window': max_candidates_per_window,
            'max_experiments_per_window': max_experiments_per_window, 'cooldown_us': cooldown_us}
        for key, ceiling in TRIGGER_CEILING.items():
            if policy[key] > ceiling:
                raise TriggerLimitError(f'policy exceeds frozen ceiling: {key}')
        self._policy = policy
        self.digest = policy_digest(policy)
        self._windows = {}
        self._last_target_us = {}

    def register_proposal(self, *, window_id, target_path, now_us):
        window = self._windows.setdefault(window_id, {'proposals': []})
        if len(window['proposals']) >= self._policy['max_proposals_per_window']:
            raise TriggerLimitError('proposal window exhausted')
        last_us = self._last_target_us.get(target_path)
        if last_us is not None and now_us - last_us < self._policy['cooldown_us']:
            raise TriggerLimitError(f'target within cooldown: {target_path}')
        window['proposals'].append(target_path)
        self._last_target_us[target_path] = now_us
        return self.digest

    def failure_modes(self, traces):
        """Aggregate failure modes from public bounded traces; empty history never triggers."""
        modes = {}
        for trace in traces:
            for action in trace.get('actions', []):
                if action.get('error'):
                    modes.setdefault(action['error'], []).append(action['action_id'])
        return modes
