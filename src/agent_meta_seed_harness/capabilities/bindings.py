"""One reviewed operation map shared by offline and Provider tools bindings."""
from . import artifact, state, scratch
from .echo import echo
from .transform import normalize_json


def ordinary_tools():
    return {'seed.echo': echo, 'seed.transform.normalize_json': normalize_json}


def resource_tools():
    return {'seed.artifact.read': artifact.read, 'seed.artifact.put': artifact.put,
        'seed.state.read': state.read, 'seed.state.write': state.write, **scratch.adapters()}
