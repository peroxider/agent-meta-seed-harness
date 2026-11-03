"""Versioned tool declarations used by the signed development package builder."""

OPERATIONS = ('seed.artifact.read', 'seed.artifact.put', 'seed.state.read', 'seed.state.write', 'seed.transform.normalize_json',
    'seed.scratch.create', 'seed.scratch.execute', 'seed.scratch.bindings', 'seed.scratch.inspect',
    'seed.scratch.export_candidate', 'seed.scratch.release')


def input_schema():
    return {'type': 'object', 'required': ['provider', 'calls'], 'properties': {
        'provider': {'const': 'fake-tools'}, 'scenario': {'enum': ['tools', 'free_text', 'sequence']},
        'calls': {'type': 'array', 'maxItems': 16, 'items': {'type': 'object', 'required': ['name', 'arguments'],
            'properties': {'name': {'type': 'string', 'maxLength': 128}, 'arguments': True}, 'additionalProperties': False}}},
        'additionalProperties': False}


def declarations(document):
    string = {'type': 'string', 'maxLength': 256}
    def object_schema(properties, required=None):
        return document({'type': 'object', 'required': list(properties) if required is None else required, 'properties': properties, 'additionalProperties': False})
    artifact_input = object_schema({'artifact_id': string})
    put_input = object_schema({'value': True})
    state_input = object_schema({'state_id': string})
    state_write_input = object_schema({'state_id': string, 'expected_state_revision_id': string, 'content_artifact_id': string})
    artifact_fields = {'artifact_id': string, 'media_type': string, 'size_bytes': {'type': 'integer', 'minimum': 0, 'maximum': 1048576}, 'sha256': {'type': 'string', 'minLength': 64, 'maxLength': 64}}
    state_fields = {'state_id': string, 'state_revision_id': string, 'content_artifact_id': string}
    ordinary = (
        ('artifact', 'seed.artifact.read', artifact_input, object_schema({**artifact_fields, 'content': {'type': 'object'}}), ['none'], [], 'PURE', 'artifact.read/v1'),
        ('artifact', 'seed.artifact.put', put_input, object_schema(artifact_fields), ['artifact.put'], ['artifact.put'], 'KEYED', 'artifact.put/v1'),
        ('state', 'seed.state.read', state_input, object_schema({**state_fields, 'value': True}), ['state.read'], ['state.read'], 'PURE', 'state.read/v1'),
        ('state', 'seed.state.write', state_write_input, object_schema(state_fields), ['state.write'], ['state.write'], 'KEYED', 'state.write/v1'),
        ('transform', 'seed.transform.normalize_json', object_schema({'json': {'type': 'string', 'maxLength': 65536}}), object_schema({'value': True}), ['none'], [], 'PURE', None),
    )
    session = {'type': 'string', 'minLength': 1, 'maxLength': 128}
    identity = {'type': 'string', 'minLength': 1, 'maxLength': 128}
    def number(maximum, minimum=0):
        return {'type': 'integer', 'minimum': minimum, 'maximum': maximum}
    def identifiers(maximum, minimum=0):
        return {'type': 'array', 'minItems': minimum, 'maxItems': maximum, 'items': identity}
    common = {'session_id': session}
    definitions = (
        ('create', {'idle_ttl_us': number(1800000000, 1), 'wall_ttl_us': number(14400000000, 1)}, [],
            ['process.spawn'], ['scratch.create','scratch.execute'], 'KEYED', 'create'),
        ('execute', {**common, 'source_artifact_id': identity, 'deadline_at_us': number(2**53-1), 'timeout_us': number(30000000,1)},
            ['session_id','source_artifact_id','deadline_at_us'], ['external.irreversible'], ['scratch.execute'], 'KEYED', 'execute'),
        ('bindings', common, ['session_id'], ['none'], ['scratch.inspect'], 'PURE', 'bindings'),
        ('inspect', {**common, 'name': identity, 'handle': identity, 'max_depth': number(32), 'max_items': number(10000),
            'max_bytes': number(1048576), 'max_ms': number(50)}, ['session_id'], ['none'], ['scratch.inspect'], 'PURE', 'inspect'),
        ('export_candidate', {**common, 'source_artifact_ids': identifiers(64,1), 'export_names': identifiers(100,1),
            'contract_artifact_id': identity, 'dependency_lock_artifact_id': identity, 'entrypoint': {'type':'string','maxLength':160},
            'dependency_artifact_ids': identifiers(64), 'support_artifact_ids': identifiers(256), 'name': identity, 'version': identity},
            ['session_id','source_artifact_ids','export_names','contract_artifact_id','dependency_lock_artifact_id','entrypoint'],
            ['artifact.put'], ['scratch.export','artifact.put'], 'KEYED', 'export'),
        ('release', common, ['session_id'], ['external.irreversible'], ['scratch.release'], 'KEYED', 'release'),
    )
    schemas = {'create':'scratch-session-receipt/v1','execute':'scratch-execution-receipt/v1',
        'bindings':'scratch-bindings-receipt/v1','inspect':'scratch-inspection-receipt/v1',
        'export':'scratch-export-receipt/v1','release':'scratch-release-receipt/v1'}
    scratch = tuple(('scratch', 'seed.scratch.'+name, object_schema(properties, required),
        document({'type':'object','required':['schema','session_id'],
            'properties':{'schema':{'const':schemas[contract]},'session_id':session}, 'additionalProperties':True}),
        effects, permissions, idem, 'scratch.'+contract+'/v1')
        for name, properties, required, effects, permissions, idem, contract in definitions)
    return ordinary + scratch
