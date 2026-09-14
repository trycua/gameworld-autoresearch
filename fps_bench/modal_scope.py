"""App-scoped admission without privileged workspace/environment configuration."""

import asyncio
from datetime import datetime, timezone

from fps_bench.modal_environment import validate_environment


def validate_app_scope(observed, plan):
    if not isinstance(plan.get("app_id"), str) or not plan["app_id"].startswith("ap-"):
        raise ValueError("Pinned app ID required for app-scoped admission")
    if not plan["app"].startswith("gameworld-"):
        raise ValueError("App-scoped admission requires a dedicated GameWorld app")
    for key in ("workspace", "environment", "environment_id", "app", "app_id"):
        if observed.get(key) != plan[key]:
            raise ValueError("Modal app scope identity changed")
    checked = datetime.fromisoformat(observed["checked_at"])
    if checked.tzinfo is None or not 0 <= (datetime.now(timezone.utc) - checked).total_seconds() <= 60:
        raise ValueError("App scope observation is stale or future-dated")
    return observed


async def inspect_app_scope(workspace_name, environment_name, app_name):
    import modal

    workspace = await modal.Workspace.from_context().hydrate.aio()
    if workspace.name != workspace_name:
        raise ValueError("Modal workspace mismatch")
    environment = await modal.Environment.from_name(environment_name).hydrate.aio()
    app = await modal.App.lookup.aio(app_name, environment_name=environment_name, create_if_missing=False)
    return {"workspace": workspace.name, "environment": environment.name, "environment_id": environment.object_id,
            "app": app_name, "app_id": app.app_id, "checked_at": datetime.now(timezone.utc).isoformat(),
            "provider_budget_enforced": False, "workspace_member_isolation": False}


async def check_scope(backend, plan):
    policy = plan.get("isolation_policy", "restricted-environment")
    if policy == "app-scoped":
        observed = await asyncio.wait_for(backend.app_scope(plan["workspace"], plan["environment"], plan["app"]), 30)
        return validate_app_scope(observed, plan)
    if policy == "restricted-environment":
        observed = await asyncio.wait_for(backend.environment(plan["workspace"], plan["environment"]), 30)
        return validate_environment(observed, plan["environment"], plan["environment_id"])
    raise ValueError("Unknown Modal isolation policy")
