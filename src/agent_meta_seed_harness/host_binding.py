"""Public Host binding. Runtime owns authority, journaling and terminal commits."""

from agent_meta_runtime.sdk.host import HarnessAdapter, HealthStatus

from .capabilities.echo import echo
from .loop import run_task
from .providers.fake import invoke_fake


async def probe(request):
    return HealthStatus("READY", "OFFLINE_ADAPTER_READY")


def create():
    return HarnessAdapter(run_task, invoke_fake, {"seed.echo": echo}, probe)
