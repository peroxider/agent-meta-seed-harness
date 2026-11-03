"""Task-free development tools binding, exclusively through the public Host."""
from agent_meta_runtime.sdk.host import HarnessAdapter, HealthStatus
from .capabilities.bindings import ordinary_tools, resource_tools
from .loop import run_task
from .providers.fake_tools import invoke_fake_tools


async def probe(request):
    return HealthStatus('READY', 'OFFLINE_TOOLS_ADAPTER_READY')


def create():
    return HarnessAdapter(run_task, invoke_fake_tools, ordinary_tools(), probe, resource_tools=resource_tools())
