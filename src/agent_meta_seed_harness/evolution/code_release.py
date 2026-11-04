"""Consumer-side explicit code-candidate release staging (S09) over public SDK contracts only.

Generation is the only stage the agent owns, and it is budget-gated and
single-pass: the staged candidate either completes or fails terminally —
there is no retry, no scheduling and no resident loop. Bundle provenance is
bound to the isolated candidate tree before anything reaches the daemon, and
activation stays the operator's signed S03 path: this module returns the
activation inputs as plain data and never signs anything.
"""
import json

from agent_meta_seed_harness.evolution.package_candidate import (
    CandidateBudget, CodeCandidateError, build_candidate_tree)
from agent_meta_seed_harness.packaging import require_bundle_inputs


class CandidateStaging:
    """One explicit staging pass: generate → bind → activation inputs.

    Every stage runs at most once; re-entering or skipping a stage is a
    terminal ``CodeCandidateError``, never a retry or a scheduled rerun.
    """

    def __init__(self, budget):
        if not isinstance(budget, CandidateBudget):
            raise CodeCandidateError('staging requires the frozen candidate budget')
        self.budget = budget
        self.tree = None
        self.stage = None

    def generate(self, *, day, generation_tokens, base_sources, overrides, version,
                 descriptor_revision, previous=None):
        if self.stage is not None:
            raise CodeCandidateError(f'staging is single-pass; stage {self.stage} already ran')
        self.budget.register_candidate(day=day, generation_tokens=generation_tokens)
        self.tree = build_candidate_tree(base_sources, overrides, version=version,
            descriptor_revision=descriptor_revision, previous=previous)
        self.stage = 'generate'
        return self.tree

    def bind(self, bundle, *, dependency_lock, contract_bundle_sha256):
        if self.stage != 'generate':
            raise CodeCandidateError('bind requires a completed generate stage')
        try:
            require_bundle_inputs(bundle, files=self.tree, dependency_lock=dependency_lock,
                contract_bundle_sha256=contract_bundle_sha256)
        except ValueError as exc:
            raise CodeCandidateError(f'candidate bundle does not match the staged tree: {exc}') from exc
        self.stage = 'bind'
        return self.tree

    def activation_inputs(self, bundle):
        """Operator-visible activation inputs as plain data; nothing is signed here."""
        if self.stage != 'bind':
            raise CodeCandidateError('activation inputs require a completed bind stage')
        manifest = json.loads(bundle.artifacts[bundle.manifest_artifact_id])
        requests = json.loads(bundle.artifacts[manifest['grant_requests_artifact_id']])['requests']
        return {'name': manifest['package_name'], 'version': manifest['package_version'],
            'manifest_artifact_id': bundle.manifest_artifact_id,
            'package_artifact_id': bundle.package_artifact_id,
            'composition_template_artifact_id': manifest['composition_template_artifact_id'],
            'grant_requests': requests}
