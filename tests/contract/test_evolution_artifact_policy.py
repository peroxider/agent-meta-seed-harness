"""SH-EVO-04 (partial): bounded trigger policy over real failure history.

The pinned-wheel-provable legs: failure modes aggregated from real task
history read through public bounded traces, an empty history that never
triggers, a hard per-window Proposal cap with per-target cooldown, a frozen
ceiling that refuses wider policies, and a deterministic policy digest. The
candidate/experiment/promotion legs stay gated (RP-06 OPEN).
"""
import asyncio

import pytest

from agent_meta_runtime.sdk import connect
from agent_meta_seed_harness.evolution.tool_trigger import TriggerLimitError, TriggerPolicy
from toolset_runtime import submit_tools, tools_environment


def refused_trigger(**kwargs):
    with pytest.raises(TriggerLimitError) as caught:
        TriggerPolicy(**kwargs)
    return caught.value


def test_trigger_policy_is_bounded_over_real_failure_history(tmp_path):
    with tools_environment(tmp_path) as (owner, actor, state, replacement):
        async def run():
            client = await connect(owner.data_dir, authority=actor)
            try:
                # Real failure history: a malformed normalize_json payload
                # fails the task through the real capability path.
                _, terminal, execution = await submit_tools(client, actor,
                    [{'name': 'seed.transform.normalize_json', 'arguments': {'json': 'not-json'}}])
                assert terminal['status'] == 'FAILED' and terminal['error'], terminal
                trace = await client.get_task_trace(terminal['task_id'])
                policy = TriggerPolicy(max_proposals_per_window=1, max_candidates_per_window=2,
                    max_experiments_per_window=2, cooldown_us=300_000_000)
                modes = policy.failure_modes([trace])
                assert modes and all(modes.values()), modes
                assert policy.failure_modes([]) == {}  # empty history never triggers
                assert policy.digest == TriggerPolicy(max_proposals_per_window=1, max_candidates_per_window=2,
                    max_experiments_per_window=2, cooldown_us=300_000_000).digest

                # One Proposal per window; the second is refused.
                target = 'artifact://sha256/' + '0' * 64
                first = policy.register_proposal(window_id='w1', target_path=target, now_us=1_000)
                assert first == policy.digest
                with pytest.raises(TriggerLimitError, match='window exhausted'):
                    policy.register_proposal(window_id='w1', target_path=target, now_us=2_000)
                # Cooldown applies per target path across the policy lifetime:
                # a fresh window cannot bypass it.
                other = 'artifact://sha256/' + '1' * 64
                with pytest.raises(TriggerLimitError, match='within cooldown'):
                    policy.register_proposal(window_id='w2', target_path=target, now_us=1_000)
                policy.register_proposal(window_id='w2', target_path=other, now_us=1_000)
                with pytest.raises(TriggerLimitError, match='within cooldown'):
                    policy.register_proposal(window_id='w3', target_path=target, now_us=1_000 + 299_999_999)
                policy.register_proposal(window_id='w3', target_path=target, now_us=1_000 + 300_000_000)

                # The agent cannot raise its own caps above the frozen ceiling.
                assert 'exceeds frozen ceiling' in str(refused_trigger(
                    max_proposals_per_window=2, max_candidates_per_window=2,
                    max_experiments_per_window=2, cooldown_us=300_000_000))
                assert 'exceeds frozen ceiling' in str(refused_trigger(
                    max_proposals_per_window=1, max_candidates_per_window=2,
                    max_experiments_per_window=2, cooldown_us=300_000_001))
            finally:
                await client.aclose()
        asyncio.run(run())
