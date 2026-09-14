"""Read-back guard for a dedicated restricted Modal pilot environment."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import importlib.metadata


PILOT_BUDGET_DOLLARS = 25


def validate_environment(observed, expected_name, expected_id=None):
    if observed.get("name") != expected_name or not expected_name.startswith("gameworld-"):
        raise ValueError("Not the dedicated GameWorld environment")
    if expected_id is not None and observed.get("environment_id") != expected_id:
        raise ValueError("Environment was replaced")
    if (not isinstance(observed.get("environment_id"), str) or not observed["environment_id"].startswith("en-")
            or observed.get("restricted") is not True or observed.get("default_member_role") != "no-access"
            or type(observed.get("max_concurrent_gpus")) is not int or observed["max_concurrent_gpus"] != 1
            or type(observed.get("max_concurrent_tasks")) is not int or observed["max_concurrent_tasks"] != 2):
        raise ValueError("Environment restriction/concurrency guard differs from pilot")
    for key in ("budget_dollars", "effective_limit_dollars", "usage_dollars"):
        if not isinstance(observed.get(key), str):
            raise ValueError("Provider monetary values must preserve decimal strings")
        try:
            value = Decimal(observed[key])
        except InvalidOperation as error:
            raise ValueError("Invalid environment monetary value") from error
        if not value.is_finite() or value < 0:
            raise ValueError("Invalid environment budget observation")
    if (Decimal(observed["budget_dollars"]) != PILOT_BUDGET_DOLLARS
            or not 0 < Decimal(observed["effective_limit_dollars"]) <= PILOT_BUDGET_DOLLARS
            or Decimal(observed["usage_dollars"]) >= Decimal(observed["effective_limit_dollars"])
            or observed.get("spend_limit_reached") is not False):
        raise ValueError("Environment budget changed, exhausted, or absent")
    checked = datetime.fromisoformat(observed["checked_at"])
    if checked.tzinfo is None or not 0 <= (datetime.now(timezone.utc) - checked).total_seconds() <= 60:
        raise ValueError("Environment observation must be fresh and UTC-aware")
    return observed


async def inspect_environment(workspace_name, environment_name):
    import modal
    from google.protobuf.empty_pb2 import Empty
    from modal.client import _Client
    from modal_proto import api_pb2

    if importlib.metadata.version("modal") != "1.5.5":
        raise ValueError("Private environment RPC mapping requires Modal 1.5.5")
    workspace = await modal.Workspace.from_context().hydrate.aio()
    if workspace.name != workspace_name:
        raise ValueError("Modal workspace mismatch")
    client = await _Client.from_env()
    response = await client.stub.EnvironmentList(Empty())
    matches = [item for item in response.items if item.name == environment_name]
    if len(matches) != 1:
        raise ValueError("Dedicated environment missing or ambiguous")
    item = matches[0]
    roles = await client.stub.EnvironmentGetRoles(api_pb2.EnvironmentGetRolesRequest(environment_id=item.environment_id))
    budget = await client.stub.EnvironmentGetBudget(api_pb2.EnvironmentGetBudgetRequest(environment_id=item.environment_id))
    return {"workspace": workspace.name, "name": item.name, "environment_id": item.environment_id,
            "restricted": item.is_managed,
            "default_member_role": "no-access" if roles.default_member_role == api_pb2.ENVIRONMENT_ROLE_NO_ACCESS else "other",
            "max_concurrent_gpus": item.max_concurrent_gpus if item.HasField("max_concurrent_gpus") else None,
            "max_concurrent_tasks": item.max_concurrent_tasks if item.HasField("max_concurrent_tasks") else None,
            "budget_dollars": str(budget.cycle_budget_dollars) if budget.HasField("cycle_budget_dollars") else None,
            "effective_limit_dollars": str(budget.effective_cycle_spend_limit),
            "usage_dollars": str(budget.current_cycle_usage), "spend_limit_reached": budget.spend_limit_reached,
            "checked_at": datetime.now(timezone.utc).isoformat(), "sdk_version": "1.5.5"}
