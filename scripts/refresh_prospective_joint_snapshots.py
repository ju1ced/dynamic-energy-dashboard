#!/usr/bin/env python3
"""Build fresh, read-only joint battery/EV snapshots from HA states."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
from typing import Any


_REQUIRED_STATE_ALIASES = (
    "battery_soc",
    "battery_device_available",
    "ev_soc",
    "ev_device_available",
    "ev_connected",
    "ev_target_soc",
    "ev_departure_utc",
    "battery_manual_override",
    "battery_local_fallback",
    "battery_acknowledgement_timed_out",
    "ev_manual_override",
    "ev_local_fallback",
    "ev_acknowledgement_timed_out",
)


class SnapshotCleanupError(OSError):
    """Raised when stale or partially written snapshots cannot be removed."""


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _extract_tool_data(result: Any) -> dict[str, Any]:
    dumped = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    if not isinstance(dumped, dict):
        raise ValueError("MCP result did not contain structured Home Assistant data")
    if dumped.get("is_error") is True:
        raise ValueError("MCP tool reported an error")
    structured = dumped.get("structured_content")
    if isinstance(structured, dict):
        data = structured.get("data")
        return data if isinstance(data, dict) else structured
    for item in dumped.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            parsed = json.loads(item.get("text", ""))
            if isinstance(parsed, dict):
                data = parsed.get("data")
                return data if isinstance(data, dict) else parsed
    raise ValueError("MCP result did not contain structured Home Assistant data")


def _map_states(
    config: dict[str, Any], raw_states: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    entities = config.get("entities")
    if not isinstance(entities, dict):
        raise ValueError("joint snapshot config must contain entities")
    missing = [alias for alias in _REQUIRED_STATE_ALIASES if alias not in entities]
    if missing:
        raise ValueError(f"joint snapshot config is missing aliases: {', '.join(missing)}")
    mapped: dict[str, dict[str, Any]] = {}
    entity_ids: list[str] = []
    for alias in _REQUIRED_STATE_ALIASES:
        entity_id = entities[alias]
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError(f"joint snapshot entity mapping is invalid: {alias}")
        entity_ids.append(entity_id)
        state = raw_states.get(entity_id)
        if not isinstance(state, dict):
            raise ValueError(f"Home Assistant response is missing configured alias: {alias}")
        mapped[alias] = state
    if len(set(entity_ids)) != len(entity_ids):
        raise ValueError("joint snapshot entity mappings must be unique")
    return mapped


async def _fetch_live_states(config: dict[str, Any], wrapper: str) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    entities = config.get("entities")
    if not isinstance(entities, dict):
        raise ValueError("joint snapshot config must contain entities")
    entity_ids = [entities.get(alias) for alias in _REQUIRED_STATE_ALIASES]
    if not all(isinstance(value, str) and value for value in entity_ids):
        raise ValueError("joint snapshot config has incomplete entity mappings")
    if len(set(entity_ids)) != len(entity_ids):
        raise ValueError("joint snapshot entity mappings must be unique")
    params = StdioServerParameters(command=wrapper, args=[])
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "ha_get_state",
                {
                    "entity_id": entity_ids,
                    "fields": ["state", "last_updated", "last_reported"],
                },
            )
    data = _extract_tool_data(result)
    raw_states = data.get("states")
    if not isinstance(raw_states, dict):
        raise ValueError("Home Assistant state response is incomplete")
    return raw_states


def _parse_instant(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a timezone-aware timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _number(value: Any, label: str, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not isfinite(parsed) or parsed < minimum or parsed > maximum:
        raise ValueError(f"{label} is outside the allowed range")
    return parsed


def _boolean(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"on", "true"}:
            return True
        if normalized in {"off", "false"}:
            return False
    raise ValueError(f"{label} must be an observed boolean state")


def _observations(
    states: dict[str, dict[str, Any]], *, captured_at: datetime, max_age: timedelta
) -> dict[str, datetime]:
    observed: dict[str, datetime] = {}
    for alias in _REQUIRED_STATE_ALIASES:
        state = states.get(alias)
        if not isinstance(state, dict):
            raise ValueError(f"missing Home Assistant state: {alias}")
        if str(state.get("state", "")).lower() in {"", "unknown", "unavailable"}:
            raise ValueError(f"Home Assistant state is unavailable: {alias}")
        instant = _parse_instant(
            state.get("last_reported") or state.get("last_updated"),
            f"{alias} observation",
        )
        if instant > captured_at:
            raise ValueError(f"Home Assistant state is future-dated: {alias}")
        if captured_at - instant > max_age:
            raise ValueError(f"Home Assistant state is stale: {alias}")
        observed[alias] = instant
    return observed


def build_joint_snapshots(
    config: dict[str, Any],
    states: dict[str, dict[str, Any]],
    *,
    captured_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return control and safety snapshots after strict freshness validation."""
    if captured_at.tzinfo is None:
        raise ValueError("captured_at must be timezone-aware")
    captured_at = captured_at.astimezone(timezone.utc)
    max_age_minutes = _number(
        config.get("max_age_minutes", 15),
        "max_age_minutes",
        minimum=1,
        maximum=60,
    )
    observed = _observations(
        states,
        captured_at=captured_at,
        max_age=timedelta(minutes=max_age_minutes),
    )
    battery_config = config.get("battery")
    ev_config = config.get("ev")
    if not isinstance(battery_config, dict) or not isinstance(ev_config, dict):
        raise ValueError("joint snapshot config must contain battery and ev objects")

    battery_soc = _number(
        states["battery_soc"]["state"], "battery SOC", minimum=0, maximum=100
    )
    ev_soc = _number(states["ev_soc"]["state"], "EV SOC", minimum=0, maximum=100)
    ev_target_soc = _number(
        states["ev_target_soc"]["state"],
        "EV target SOC",
        minimum=0,
        maximum=100,
    )
    departure = _parse_instant(states["ev_departure_utc"]["state"], "EV departure")
    minimum_soc = _number(
        battery_config.get("minimum_soc_percent"),
        "battery minimum SOC",
        minimum=0,
        maximum=100,
    )
    maximum_soc = _number(
        battery_config.get("maximum_soc_percent"),
        "battery maximum SOC",
        minimum=0,
        maximum=100,
    )
    if minimum_soc >= maximum_soc:
        raise ValueError("battery minimum SOC must be below maximum SOC")
    if departure <= captured_at:
        raise ValueError("EV departure must be after capture")
    if ev_target_soc < ev_soc:
        raise ValueError("EV target SOC must not be below current SOC")

    battery_observed = min(
        observed["battery_soc"],
        observed["battery_device_available"],
        observed["battery_manual_override"],
        observed["battery_local_fallback"],
        observed["battery_acknowledgement_timed_out"],
    )
    ev_observed = min(
        observed["ev_soc"],
        observed["ev_device_available"],
        observed["ev_connected"],
        observed["ev_target_soc"],
        observed["ev_departure_utc"],
        observed["ev_manual_override"],
        observed["ev_local_fallback"],
        observed["ev_acknowledgement_timed_out"],
    )
    snapshot_observed = min(battery_observed, ev_observed).isoformat()

    generation_id = uuid.uuid4().hex
    control = {
        "snapshot_generation_id": generation_id,
        "observed_at": snapshot_observed,
        "battery": {
            "soc_percent": battery_soc,
            "minimum_soc_percent": minimum_soc,
            "maximum_soc_percent": maximum_soc,
            "usable_capacity_kwh": _number(
                battery_config.get("usable_capacity_kwh"),
                "battery usable capacity",
                minimum=0.001,
                maximum=1000,
            ),
            "max_charge_power_kw": _number(
                battery_config.get("max_charge_power_kw"),
                "battery max charge power",
                minimum=0,
                maximum=1000,
            ),
            "max_discharge_power_kw": _number(
                battery_config.get("max_discharge_power_kw"),
                "battery max discharge power",
                minimum=0,
                maximum=1000,
            ),
            "controller_owner": "SMA",
            "observed_at": battery_observed.isoformat(),
        },
        "ev": {
            "connected": _boolean(states["ev_connected"]["state"], "EV connected"),
            "soc_percent": ev_soc,
            "target_soc_percent": ev_target_soc,
            "usable_capacity_kwh": _number(
                ev_config.get("usable_capacity_kwh"),
                "EV usable capacity",
                minimum=0.001,
                maximum=1000,
            ),
            "departure_utc": departure.isoformat(),
            "max_charge_power_kw": _number(
                ev_config.get("max_charge_power_kw"),
                "EV max charge power",
                minimum=0,
                maximum=1000,
            ),
            "controller_owner": "SMAPPEE",
            "observed_at": ev_observed.isoformat(),
        },
    }
    safety = {
        "snapshot_generation_id": generation_id,
        "observed_at": snapshot_observed,
        "battery": {
            "device_available": _boolean(
                states["battery_device_available"]["state"],
                "battery device available",
            ),
            "controller_owner": "SMA",
            "manual_override_active": _boolean(
                states["battery_manual_override"]["state"],
                "battery manual override",
            ),
            "local_fallback_active": _boolean(
                states["battery_local_fallback"]["state"],
                "battery local fallback",
            ),
            "acknowledgement_timed_out": _boolean(
                states["battery_acknowledgement_timed_out"]["state"],
                "battery acknowledgement timeout",
            ),
            "soc_percent": battery_soc,
        },
        "ev": {
            "device_available": _boolean(
                states["ev_device_available"]["state"], "EV device available"
            ),
            "controller_owner": "SMAPPEE",
            "manual_override_active": _boolean(
                states["ev_manual_override"]["state"], "EV manual override"
            ),
            "local_fallback_active": _boolean(
                states["ev_local_fallback"]["state"], "EV local fallback"
            ),
            "acknowledgement_timed_out": _boolean(
                states["ev_acknowledgement_timed_out"]["state"],
                "EV acknowledgement timeout",
            ),
            "connected": _boolean(states["ev_connected"]["state"], "EV connected"),
            "soc_percent": ev_soc,
        },
    }
    return control, safety


def persist_snapshot_pair(
    control_path: Path,
    safety_path: Path,
    control: dict[str, Any],
    safety: dict[str, Any],
) -> None:
    """Write a generation-bound pair or remove both outputs on failure."""
    paths_and_values = ((control_path, control), (safety_path, safety))
    temporary_paths: list[tuple[Path, Path]] = []
    try:
        for path, value in paths_and_values:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            )
            temporary = Path(handle.name)
            with handle:
                json.dump(value, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            temporary_paths.append((temporary, path))
        _remove_snapshot_pair(control_path, safety_path)
        try:
            for temporary, path in temporary_paths:
                os.replace(temporary, path)
        except Exception as replace_error:
            try:
                _remove_snapshot_pair(control_path, safety_path)
            except OSError as cleanup_error:
                raise SnapshotCleanupError(
                    "partial snapshot pair could not be removed"
                ) from cleanup_error
            raise replace_error
    finally:
        for temporary, _ in temporary_paths:
            temporary.unlink(missing_ok=True)


def _remove_snapshot_pair(control_path: Path, safety_path: Path) -> None:
    errors: list[OSError] = []
    for path in (control_path, safety_path):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(exc)
    if errors:
        raise errors[0]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh fail-closed joint dry-run snapshots from Home Assistant"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/private/prospective-joint-snapshot-source.json"),
    )
    parser.add_argument("--states-fixture", type=Path)
    parser.add_argument(
        "--wrapper", default=str(Path.home() / ".hermes/bin/home-assistant-mcp-wrapper")
    )
    parser.add_argument(
        "--control-output",
        type=Path,
        default=Path("config/private/prospective-joint-control-inputs.json"),
    )
    parser.add_argument(
        "--safety-output",
        type=Path,
        default=Path("config/private/prospective-joint-safety-state.json"),
    )
    parser.add_argument("--now")
    parser.add_argument("--soft-fail", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _remove_snapshot_pair(args.control_output, args.safety_output)
    except OSError as exc:
        print(
            json.dumps(
                {
                    "status": "REJECTED",
                    "reason": f"SNAPSHOT_CLEANUP_FAILED:{type(exc).__name__}",
                    "execution_allowed": False,
                    "physical_writes": False,
                    "home_assistant_writes": False,
                    "sma_writes": False,
                    "smappee_writes": False,
                }
            )
        )
        return 2
    try:
        config = _load_object(args.config)
        captured_at = (
            _parse_instant(args.now, "now")
            if args.now
            else datetime.now(timezone.utc)
        )
        if args.states_fixture:
            fixture = _load_object(args.states_fixture)
            raw_states = fixture.get("states")
            if not isinstance(raw_states, dict):
                raise ValueError("states fixture must contain a states object")
        else:
            raw_states = asyncio.run(_fetch_live_states(config, args.wrapper))
        states = _map_states(config, raw_states)
        control, safety = build_joint_snapshots(
            config, states, captured_at=captured_at
        )
        try:
            persist_snapshot_pair(
                args.control_output, args.safety_output, control, safety
            )
        except SnapshotCleanupError:
            raise
        except OSError as exc:
            raise SnapshotCleanupError("snapshot persistence failed") from exc
        print(
            json.dumps(
                {
                    "status": "READY",
                    "observed_at": control["observed_at"],
                    "execution_allowed": False,
                    "physical_writes": False,
                    "home_assistant_writes": False,
                    "sma_writes": False,
                    "smappee_writes": False,
                }
            )
        )
        return 0
    except SnapshotCleanupError as exc:
        print(
            json.dumps(
                {
                    "status": "REJECTED",
                    "reason": f"SNAPSHOT_CLEANUP_FAILED:{type(exc.__cause__).__name__}",
                    "execution_allowed": False,
                    "physical_writes": False,
                    "home_assistant_writes": False,
                    "sma_writes": False,
                    "smappee_writes": False,
                }
            )
        )
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "REJECTED",
                    "reason": f"REFRESH_FAILED:{type(exc).__name__}",
                    "execution_allowed": False,
                    "physical_writes": False,
                    "home_assistant_writes": False,
                    "sma_writes": False,
                    "smappee_writes": False,
                }
            )
        )
        return 0 if args.soft_fail else 2


if __name__ == "__main__":
    sys.exit(main())
