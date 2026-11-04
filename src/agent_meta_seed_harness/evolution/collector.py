"""Consumer-side Evolution evidence collector (S07) over public SDK contracts only.

Task history is read through public bounded traces and aggregated into an
evidence fixture. Every evidence reference is resolved fail-closed — against
the observed history (fact/action references appear in real traces) or the
public Artifact store (manifest lookup) — before any Proposal is authored.
Missing, unknown or malformed evidence raises :class:`InsufficientEvidence`
and commits nothing; the collector never fabricates a pass. The Runtime
records ``source_evidence_ids`` as opaque strings, so resolution is entirely
Seed-side responsibility.
"""
from agent_meta_runtime.sdk import StableError
from agent_meta_runtime.sdk.packages import canonical_json

EVIDENCE_SCHEMA = 'seed-evolution-evidence/v1'


class InsufficientEvidence(Exception):
    """Fail-closed exit: evidence cannot be resolved from observed history."""


class EvidenceCollector:
    def __init__(self, client, authority, *, realm_id='realm://main'):
        self._client = client
        self._authority = authority
        self._realm_id = realm_id

    async def collect(self, task_ids, *, hypothesis, target_composition_id,
                      additional_evidence_ids=(), redaction_policy_artifact_id=None):
        if not task_ids:
            raise InsufficientEvidence('no task history requested')
        traces = {}
        for task_id in task_ids:
            try:
                traces[task_id] = await self._client.get_task_trace(task_id)
            except StableError as error:
                raise InsufficientEvidence(f'task history unavailable: {task_id}') from error
        observed = set()
        for trace in traces.values():
            for action in trace.get('actions', []):
                observed.add(action['action_id'])
            for edge in trace.get('edges', []):
                observed.add(edge['source_fact_id'])
                observed.add(edge['to_id'])
        evidence_ids = sorted(reference for reference in observed if reference.startswith('fact://'))
        for reference in additional_evidence_ids:
            await self._resolve(reference, observed)
            if reference not in evidence_ids:
                evidence_ids.append(reference)
        summary = {'schema': EVIDENCE_SCHEMA, 'hypothesis': hypothesis,
            'target_composition_id': target_composition_id,
            'redaction_policy_artifact_id': redaction_policy_artifact_id,
            'tasks': [self._summarize(trace) for trace in traces.values()],
            'source_fact_ids': sorted(reference for reference in observed if reference.startswith('fact://'))}
        put = await self._client.put_artifact(realm_id=self._realm_id, actor_id=self._authority.actor_id,
            content=canonical_json(summary), kind='evidence', media_type='application/json')
        evidence_ids.append(put['artifact_id'])
        proposal = await self._client.propose(realm_id=self._realm_id, actor_id=self._authority.actor_id,
            hypothesis=hypothesis, target_composition_id=target_composition_id,
            source_evidence_ids=evidence_ids)
        return {'proposal_id': proposal.resource['proposal_id'], 'evidence_artifact_id': put['artifact_id'],
            'source_evidence_ids': evidence_ids, 'summary': summary}

    async def _resolve(self, reference, observed):
        if reference.startswith('artifact://'):
            try:
                await self._client.get_artifact_manifest(reference)
            except StableError as error:
                raise InsufficientEvidence(f'artifact evidence unavailable: {reference}') from error
        elif reference in observed:
            return
        else:
            raise InsufficientEvidence(f'evidence not in observed history: {reference}')

    def _summarize(self, trace):
        actions = [{'action_id': action['action_id'], 'intent': action.get('intent'),
            'status': action.get('status'), 'error': action.get('error')} for action in trace.get('actions', [])]
        return {'task_id': trace['task_id'], 'status': trace.get('status'), 'actions': actions,
            'failure_modes': sorted({action['error'] for action in actions if action['error']})}
