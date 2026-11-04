"""Consumer-side artifact-candidate construction (S08) over public SDK contracts only.

Every S08 candidate replaces or adds a whitelisted non-executable artifact
(tool descriptor, skill document, prompt policy). The builder binds each
candidate to the hash of the live old value read through the public Artifact
store, refuses stale expected hashes, refuses kinds outside the whitelist,
and refuses a candidate that targets its own frozen evaluator — the fail-closed
governance legs of SH-GOV-03 that are provable on the pinned wheel. Nothing
here fabricates experiment or promotion results; the full pipeline stays
gated (RP-06 OPEN).
"""
import json

from agent_meta_runtime.sdk import StableError
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex

ARTIFACT_KIND_WHITELIST = frozenset({'tool_descriptor', 'skill_doc', 'prompt_policy'})


class ArtifactCandidateError(Exception):
    """Fail-closed exit: the candidate cannot be built under S08 governance."""


async def load_old_value(client, authority, *, realm_id, target_artifact_id):
    """Read the live old value through the public store; return (content, sha256)."""
    try:
        content = await client.get_artifact_content(target_artifact_id)
    except StableError as error:
        raise ArtifactCandidateError(f'target artifact unavailable: {target_artifact_id}') from error
    return content, sha256_hex(content)


def build_candidate(*, kind, target_artifact_id, expected_old_value_sha256, observed_old_value_sha256,
                    new_value, criteria_artifact_id, criteria_sha256):
    if kind not in ARTIFACT_KIND_WHITELIST:
        raise ArtifactCandidateError(f'artifact kind outside whitelist: {kind}')
    if expected_old_value_sha256 != observed_old_value_sha256:
        raise ArtifactCandidateError('stale expected old value hash')
    if target_artifact_id == criteria_artifact_id:
        raise ArtifactCandidateError('candidate may not replace its own evaluator')
    candidate = {'kind': kind, 'target_artifact_id': target_artifact_id,
        'expected_old_value_sha256': expected_old_value_sha256,
        'new_value': new_value, 'new_value_sha256': sha256_hex(canonical_json(new_value)),
        'criteria_artifact_id': criteria_artifact_id, 'frozen_criteria_sha256': criteria_sha256}
    return candidate


def preview_diff(old_content, candidate):
    """Canonical approval preview: hash diff and the affected call surface."""
    old_value = json.loads(old_content)
    changed_paths = sorted({key for key in set(old_value) | set(candidate['new_value'])
        if old_value.get(key) != candidate['new_value'].get(key)})
    return {'artifact_kind': candidate['kind'], 'target_artifact_id': candidate['target_artifact_id'],
        'old_value_sha256': candidate['expected_old_value_sha256'],
        'new_value_sha256': candidate['new_value_sha256'], 'changed_paths': changed_paths}
