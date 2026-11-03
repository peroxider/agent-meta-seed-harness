"""Provider tools binding; credentials and requests stay with controlled Root."""
from agent_meta_runtime.sdk.host import HarnessAdapter, HealthStatus
from .capabilities.bindings import ordinary_tools, resource_tools
from .loop import run_task
from .provider_config import CONFIGURATION
from .providers.messages import MessagesProvider


async def probe(request):
    return HealthStatus('READY', 'PROVIDER_TOOLS_ADAPTER_READY')


def create():
    return HarnessAdapter(run_task, None, ordinary_tools(), probe,
        resource_tools=resource_tools(), provider=MessagesProvider(**CONFIGURATION).adapter())
