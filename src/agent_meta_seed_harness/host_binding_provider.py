"""Task-free binding for an explicitly signed Provider configuration."""
from agent_meta_runtime.sdk.host import HarnessAdapter, HealthStatus
from .capabilities.echo import echo
from .loop import run_task
from .provider_config import CONFIGURATION
from .providers.messages import MessagesProvider


async def probe(request):
    return HealthStatus('READY','PROVIDER_PLAN_ADAPTER_READY')


def create():
    return HarnessAdapter(run_task,None,{'seed.echo':echo},probe,
        provider=MessagesProvider(**CONFIGURATION).adapter())
