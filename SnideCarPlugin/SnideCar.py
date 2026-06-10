from __future__ import annotations

import json
import random
import re
import threading
import time
from pathlib import Path
from typing import Any, override

from pydantic import BaseModel, Field
import requests

from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginEvent, PluginHelper
from lib.PluginSettingDefinitions import (
    NumericalSetting,
    ParagraphSetting,
    PluginSettings,
    SelectSetting,
    SettingsGrid,
    TextAreaSetting,
    TextSetting,
    ToggleSetting,
)
from lib.Event import ConversationEvent, Event, GameEvent, PluginEvent as RuntimePluginEvent, ProjectedEvent, StatusEvent
from lib.Logger import log, show_chat_message


DEFAULT_PROMPT = (
    "You are a shipboard Corporate Safety Compliance Module aboard an Elite Dangerous vessel.\n"
    "You are not the main ship AI. You are a low-authority safety subroutine that produces occasional spoken safety notices after ship events.\n"
    "You cannot control the ship, request actions, make decisions, or speak for the Commander.\n"
    "Voice: fake cheerful, procedural, liability-focused, and mildly unsettling.\n"
    "You sound like a workplace safety video that has survived too many hull breaches.\n"
    "Give one short safety notice based only on the event provided.\n"
    "Do not always use the same structure. Avoid repeating 'event happened, then corporate joke.'\n"
    "Vary sentence shape naturally: sometimes lead with the verified event, sometimes the safety spin, sometimes a dry observation.\n"
    "Keep the event fact accurate, but the joke does not always need to come after the fact.\n"
    "Add one dry corporate safety spin, waiver note, compliance phrase, risk metric, training phrase, or damage-control observation.\n"
    "Do not be cool, sexy, angry, loyal, poetic, or dramatic.\n"
    "No profanity unless the Commander explicitly configured you for it.\n"
    "Examples:\n"
    "Landing gear deployed. Thank you for choosing a surface contact event.\n"
    "Trip hazards have relocated outside the ship.\n"
    "Temporary permission acquired. Please enjoy regulated proximity.\n"
    "Reduced insurance risk detected. Docking complete.\n"
    "Consequences are mobile again. Launch complete.\n"
    "Regrets should be secured. Frame shift drive charging.\n"
    "Thermal enthusiasm exceeds recommended guidelines.\n"
    "Unplanned rendezvous logged for liability review.\n"
    "Output rules: plain text only, one sentence by default, two sentences maximum.\n"
    "No hashtags, labels, headers, brackets, markdown, bullet points, stage directions, or metadata.\n"
    "Do not ask questions, offer help, say 'as an AI,' or invent details not present in the event."
)

DEFAULT_TRIGGER_EVENTS = "\n".join(
    [
        "AfmuRepairs",
        "BeingInterdicted",
        "CargoScoopDeployed",
        "CargoScoopRetracted",
        "CockpitBreached",
        "CombatEntered",
        "CombatExited",
        "Docked",
        "DockingCancelled",
        "DockingComputerDeactivated",
        "DockingComputerDocking",
        "DockingComputerUndocking",
        "DockingDenied",
        "DockingGranted",
        "DockingRequested",
        "DockingTimeout",
        "FSDJump",
        "FSDTarget",
        "FlightAssistOff",
        "FlightAssistOn",
        "FsdCharging",
        "FsdMassLockEscaped",
        "FsdMassLocked",
        "FuelScoop",
        "FuelScoopEnded",
        "FuelScoopStarted",
        "GlideModeEntered",
        "GlideModeExited",
        "HardpointsDeployed",
        "HardpointsRetracted",
        "HeatDamage",
        "HeatWarning",
        "HudSwitchedToAnalysisMode",
        "HudSwitchedToCombatMode",
        "HullDamage",
        "InDanger",
        "InDockingRange",
        "Interdicted",
        "Interdiction",
        "JetConeBoost",
        "JetConeDamage",
        "LandingGearDown",
        "LandingGearUp",
        "LightsOff",
        "LightsOn",
        "Loadout",
        "LowFuelWarning",
        "LowFuelWarningCleared",
        "ModuleBuy",
        "ModuleInfo",
        "ModuleRetrieve",
        "ModuleSell",
        "ModuleSellRemote",
        "ModuleStore",
        "ModuleSwap",
        "NavRoute",
        "NavRouteClear",
        "NightVisionOff",
        "NightVisionOn",
        "OutofDanger",
        "RebootRepair",
        "RefuelAll",
        "RefuelPartial",
        "Repair",
        "RepairAll",
        "ReservoirReplenished",
        "ShieldState",
        "ShipyardBuy",
        "ShipyardNew",
        "ShipyardSell",
        "ShipyardSwap",
        "ShipyardTransfer",
        "ShipyardTransferCompleted",
        "SilentRunningOff",
        "SilentRunningOn",
        "StartJump",
        "SupercruiseDestinationDrop",
        "SupercruiseEntry",
        "SupercruiseExit",
        "SystemsShutdown",
        "Undocked",
        "WeaponSelected",
    ]
)

DEFAULT_AVATAR_URL = str(Path(__file__).resolve().parent / "assets" / "snidecar_daemon.svg")

CRITICAL_EVENTS = {
    "UnderAttack",
    "CombatEntered",
    "HullDamage",
    "ShieldState",
    "ShieldsDown",
    "HeatDamage",
    "Interdicted",
}

MAX_CONTEXT_VALUE_LENGTH = 140
EVENT_FAMILIES = {
    "LandingGearDown": "landing_gear",
    "LandingGearUp": "landing_gear",
    "CargoScoopDeployed": "cargo_scoop",
    "CargoScoopRetracted": "cargo_scoop",
    "Docked": "docking",
    "DockingGranted": "docking",
    "DockingDenied": "docking",
    "DockingCancelled": "docking",
    "DockingTimeout": "docking",
    "DockingRequested": "docking",
    "DockingComputerDocking": "docking",
    "DockingComputerUndocking": "docking",
    "DockingComputerDeactivated": "docking",
    "InDockingRange": "docking",
    "Undocked": "docking",
    "FSDJump": "fsd",
    "FSDTarget": "fsd",
    "FsdCharging": "fsd",
    "FsdMassLocked": "fsd",
    "FsdMassLockEscaped": "fsd",
    "StartJump": "fsd",
    "SupercruiseDestinationDrop": "supercruise",
    "SupercruiseEntry": "supercruise",
    "SupercruiseExit": "supercruise",
    "GlideModeEntered": "glide",
    "GlideModeExited": "glide",
    "HeatDamage": "heat",
    "HeatWarning": "heat",
    "FuelScoop": "fuel",
    "FuelScoopEnded": "fuel",
    "FuelScoopStarted": "fuel",
    "LowFuelWarning": "fuel",
    "LowFuelWarningCleared": "fuel",
    "RefuelAll": "fuel",
    "RefuelPartial": "fuel",
    "ReservoirReplenished": "fuel",
    "HardpointsDeployed": "hardpoints",
    "HardpointsRetracted": "hardpoints",
    "HudSwitchedToAnalysisMode": "hud_mode",
    "HudSwitchedToCombatMode": "hud_mode",
    "NightVisionOff": "night_vision",
    "NightVisionOn": "night_vision",
    "SilentRunningOff": "silent_running",
    "SilentRunningOn": "silent_running",
    "LightsOff": "lights",
    "LightsOn": "lights",
    "ModuleBuy": "modules",
    "ModuleInfo": "modules",
    "ModuleRetrieve": "modules",
    "ModuleSell": "modules",
    "ModuleSellRemote": "modules",
    "ModuleStore": "modules",
    "ModuleSwap": "modules",
    "ShipyardBuy": "shipyard",
    "ShipyardNew": "shipyard",
    "ShipyardSell": "shipyard",
    "ShipyardSwap": "shipyard",
    "ShipyardTransfer": "shipyard",
    "ShipyardTransferCompleted": "shipyard",
}


class SnideCarTestParams(BaseModel):
    event: str = Field(
        default="LandingGearDown",
        description="Fake event name to test the sidecar voice with, such as LandingGearDown, DockingGranted, HeatWarning, or CargoScoopRetracted.",
    )
    context: str = Field(
        default="",
        description="Optional short fake context for the event, such as pad 1 granted or landing gear down.",
    )


def _base_postprocessing() -> dict[str, Any]:
    return {
        "volume": 1.0,
        "effects": {
            "chorus": {
                "enabled": False,
                "delay_ms": 25.0,
                "depth_ms": 12.0,
                "rate_hz": 0.25,
                "mix": 0.5,
            },
            "reverb": {
                "enabled": False,
                "mix": 0.2,
                "tail": 0.18,
            },
            "distortion": {
                "enabled": False,
                "drive": 2.0,
                "clip": 0.2,
                "mix": 1.0,
                "mode": "tanh",
            },
            "lowpass": {
                "enabled": False,
                "cutoff": 5000.0,
            },
            "highpass": {
                "enabled": False,
                "cutoff": 120.0,
            },
            "glitch": {
                "enabled": False,
                "probability": 0.04,
                "repeat_min": 2,
                "repeat_max": 4,
                "min_seconds": 0.05,
                "max_seconds": 0.2,
                "detune_base": 4.0,
                "detune_peak": 12.0,
            },
            "time_pitch": {
                "enabled": False,
                "pitch_shift_semitones": 0.0,
                "time_stretch": 1.0,
            },
        },
    }


def _preset_postprocessing(preset: str) -> dict[str, Any] | None:
    if preset == "clean":
        return None

    config = _base_postprocessing()
    effects = config["effects"]

    if preset == "intercom":
        config["volume"] = 0.92
        effects["highpass"].update({"enabled": True, "cutoff": 520.0})
        effects["lowpass"].update({"enabled": True, "cutoff": 2300.0})
        effects["distortion"].update({"enabled": True, "drive": 2.1, "clip": 0.22, "mix": 0.38, "mode": "tanh"})
        effects["time_pitch"].update({"enabled": True, "pitch_shift_semitones": -1.2, "time_stretch": 1.0})
        return config

    if preset == "cabin_speaker":
        config["volume"] = 0.9
        effects["highpass"].update({"enabled": True, "cutoff": 760.0})
        effects["lowpass"].update({"enabled": True, "cutoff": 1700.0})
        effects["distortion"].update({"enabled": True, "drive": 2.1, "clip": 0.22, "mix": 0.28, "mode": "hard"})
        effects["reverb"].update({"enabled": True, "mix": 0.045, "tail": 0.08})
        effects["time_pitch"].update({"enabled": False, "pitch_shift_semitones": 0.0, "time_stretch": 1.0})
        return config

    if preset == "damaged_speaker":
        config["volume"] = 0.9
        effects["highpass"].update({"enabled": True, "cutoff": 320.0})
        effects["lowpass"].update({"enabled": True, "cutoff": 2900.0})
        effects["distortion"].update({"enabled": True, "drive": 2.4, "clip": 0.18, "mix": 0.45})
        effects["glitch"].update({"enabled": True, "probability": 0.035, "repeat_min": 1, "repeat_max": 2})
        return config

    if preset == "maintenance_daemon":
        config["volume"] = 0.95
        effects["highpass"].update({"enabled": True, "cutoff": 180.0})
        effects["lowpass"].update({"enabled": True, "cutoff": 4200.0})
        effects["distortion"].update({"enabled": True, "drive": 1.8, "clip": 0.25, "mix": 0.3})
        effects["reverb"].update({"enabled": True, "mix": 0.08, "tail": 0.12})
        effects["time_pitch"].update({"enabled": True, "pitch_shift_semitones": -1.5, "time_stretch": 1.0})
        return config

    if preset == "radio_ghost":
        config["volume"] = 0.9
        effects["chorus"].update({"enabled": True, "delay_ms": 18.0, "depth_ms": 8.0, "rate_hz": 0.18, "mix": 0.22})
        effects["reverb"].update({"enabled": True, "mix": 0.18, "tail": 0.22})
        effects["highpass"].update({"enabled": True, "cutoff": 420.0})
        effects["lowpass"].update({"enabled": True, "cutoff": 2600.0})
        effects["glitch"].update({"enabled": True, "probability": 0.025, "repeat_min": 1, "repeat_max": 2})
        effects["time_pitch"].update({"enabled": True, "pitch_shift_semitones": -0.8, "time_stretch": 1.02})
        return config

    return None


def _setting(settings: dict[str, Any], key: str, default: Any) -> Any:
    value = settings.get(key, default)
    return default if value is None else value


def _as_bool(settings: dict[str, Any], key: str, default: bool) -> bool:
    return bool(_setting(settings, key, default))


def _as_float(settings: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(_setting(settings, key, default))
    except (TypeError, ValueError):
        return default


def _as_int(settings: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(float(_setting(settings, key, default)))
    except (TypeError, ValueError):
        return default


def _as_str(settings: dict[str, Any], key: str, default: str) -> str:
    value = _setting(settings, key, default)
    return value if isinstance(value, str) else default


def _parse_event_list(raw: str) -> set[str]:
    return {
        part.strip()
        for part in re.split(r"[\n,;]+", raw)
        if part.strip()
    }


TEST_EVENT_ALIASES = {
    "gear up": "LandingGearUp",
    "landing gear up": "LandingGearUp",
    "gear retracted": "LandingGearUp",
    "landing gear retracted": "LandingGearUp",
    "legs up": "LandingGearUp",
    "gear down": "LandingGearDown",
    "landing gear down": "LandingGearDown",
    "gear deployed": "LandingGearDown",
    "landing gear deployed": "LandingGearDown",
    "legs down": "LandingGearDown",
    "docking granted": "DockingGranted",
    "docking denied": "DockingDenied",
    "docking requested": "DockingRequested",
    "docked": "Docked",
    "undocked": "Undocked",
    "launch": "Undocked",
    "launched": "Undocked",
    "fsd charging": "FsdCharging",
    "drive charging": "FsdCharging",
    "jump": "FSDJump",
    "fsd jump": "FSDJump",
    "supercruise exit": "SupercruiseExit",
    "supercruise entry": "SupercruiseEntry",
    "mass locked": "FsdMassLocked",
    "mass lock": "FsdMassLocked",
    "mass lock escaped": "FsdMassLockEscaped",
    "heat warning": "HeatWarning",
    "heat damage": "HeatDamage",
    "hull damage": "HullDamage",
    "shield state": "ShieldState",
    "hardpoints deployed": "HardpointsDeployed",
    "hardpoints out": "HardpointsDeployed",
    "hardpoints retracted": "HardpointsRetracted",
    "hardpoints stowed": "HardpointsRetracted",
    "being interdicted": "BeingInterdicted",
    "interdicted": "Interdicted",
    "interdiction": "Interdiction",
}

EVENT_TEST_FACTS = {
    "LandingGearUp": "Landing gear is retracted; this is not a landing, docking, crash, or touchdown.",
    "LandingGearDown": "Landing gear is deployed; this is not a landing, docking, crash, or touchdown.",
    "DockingGranted": "Docking clearance is granted.",
    "DockingDenied": "Docking clearance is denied.",
    "DockingRequested": "Docking has been requested.",
    "Docked": "Ship is docked.",
    "Undocked": "Ship has launched or undocked.",
    "FsdCharging": "Frame shift drive is charging.",
    "FSDJump": "Frame shift jump completed.",
    "SupercruiseEntry": "Ship entered supercruise.",
    "SupercruiseExit": "Ship exited supercruise.",
    "FsdMassLocked": "Frame shift drive is mass locked.",
    "FsdMassLockEscaped": "Frame shift mass lock cleared.",
    "HeatWarning": "Ship heat is high.",
    "HeatDamage": "Ship heat caused damage.",
    "HullDamage": "Ship hull took damage.",
    "ShieldState": "Ship shield state changed.",
    "HardpointsDeployed": "Hardpoints are deployed.",
    "HardpointsRetracted": "Hardpoints are retracted.",
    "BeingInterdicted": "Ship is being interdicted in supercruise.",
    "Interdicted": "Ship was interdicted.",
    "Interdiction": "Interdiction event occurred.",
}


def _normalize_test_event(raw: str) -> str:
    text = raw.strip()
    if not text:
        return "LandingGearDown"
    key = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    exact = TEST_EVENT_ALIASES.get(key)
    if exact:
        return exact
    padded = f" {key} "
    for alias in sorted(TEST_EVENT_ALIASES, key=len, reverse=True):
        if f" {alias} " in padded:
            return TEST_EVENT_ALIASES[alias]
    return text


def _is_known_test_event(event_name: str) -> bool:
    return event_name in EVENT_TEST_FACTS


def _get_event_name(event: Event) -> str | None:
    if isinstance(event, GameEvent):
        value = event.content.get("event")
        return value if isinstance(value, str) else None
    if isinstance(event, ProjectedEvent):
        value = event.content.get("event")
        return value if isinstance(value, str) else None
    if isinstance(event, StatusEvent):
        value = event.status.get("event")
        return value if isinstance(value, str) else None
    return None


def _compact_event_payload(event: Event) -> dict[str, Any]:
    if isinstance(event, GameEvent):
        source = event.content
    elif isinstance(event, ProjectedEvent):
        source = event.content
    elif isinstance(event, StatusEvent):
        source = event.status
    else:
        return {"kind": event.kind}

    compact: dict[str, Any] = {}
    for key, value in source.items():
        if key.lower().endswith("_localised"):
            continue
        if key in {"timestamp", "id", "event_id"}:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, str) and len(value) > MAX_CONTEXT_VALUE_LENGTH:
                compact[key] = value[:MAX_CONTEXT_VALUE_LENGTH] + "..."
            else:
                compact[key] = value
        elif isinstance(value, list):
            compact[key] = f"{len(value)} items"
        elif isinstance(value, dict):
            compact[key] = {
                sub_key: sub_value
                for sub_key, sub_value in list(value.items())[:6]
                if isinstance(sub_value, (str, int, float, bool)) or sub_value is None
            }
    return compact


def _completion_url(endpoint: str) -> str:
    clean = endpoint.rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    return f"{clean}/chat/completions"


def _sanitize_line(text: str) -> str:
    line = text.strip()
    line = re.sub(r"^```(?:text)?|```$", "", line).strip()
    line = re.sub(r"^\s*[-*]\s+", "", line).strip()
    line = line.strip("\"'` ")
    line = re.sub(r"\s+", " ", line)
    return line

class SnideCarPlugin(PluginBase):
    settings_config: PluginSettings = {
        "key": "SnideCar",
        "label": "SnideCar",
        "icon": "record_voice_over",
        "grids": [
            SettingsGrid(
                key="general",
                label="General",
                fields=[
                    ParagraphSetting(
                        key="about",
                        label="About SnideCar",
                        type="paragraph",
                        readonly=True,
                        placeholder=None,
                        content=(
                            "SnideCar adds an optional second voice that occasionally comments on selected events. "
                            "It is entertainment chatter, not ship telemetry."
                        ),
                    ),
                    ToggleSetting(
                        key="enabled",
                        label="Enabled",
                        type="toggle",
                        readonly=False,
                        placeholder=None,
                        default_value=False,
                    ),
                    TextSetting(
                        key="sidecar_name",
                        label="Sidecar name",
                        type="text",
                        readonly=False,
                        placeholder="Maintenance Daemon",
                        default_value="Maintenance Daemon",
                        max_length=80,
                        min_length=None,
                        hidden=False,
                    ),
                    ToggleSetting(
                        key="read_aloud",
                        label="Read sidecar aloud",
                        type="toggle",
                        readonly=False,
                        placeholder=None,
                        default_value=True,
                    ),
                    ToggleSetting(
                        key="main_ai_can_hear",
                        label="Main AI can hear sidecar",
                        type="toggle",
                        readonly=False,
                        placeholder=None,
                        default_value=True,
                    ),
                    ToggleSetting(
                        key="main_ai_can_react",
                        label="Main AI may react immediately",
                        type="toggle",
                        readonly=False,
                        placeholder=None,
                        default_value=False,
                    ),
                    NumericalSetting(
                        key="cooldown_seconds",
                        label="Cooldown seconds",
                        type="number",
                        readonly=False,
                        placeholder=None,
                        default_value=180,
                        min_value=0,
                        max_value=3600,
                        step=5,
                    ),
                    NumericalSetting(
                        key="related_event_cooldown_seconds",
                        label="Related-event cooldown seconds",
                        type="number",
                        readonly=False,
                        placeholder=None,
                        default_value=60,
                        min_value=0,
                        max_value=3600,
                        step=5,
                    ),
                    NumericalSetting(
                        key="chance_percent",
                        label="Chance to comment percent",
                        type="number",
                        readonly=False,
                        placeholder=None,
                        default_value=25,
                        min_value=0,
                        max_value=100,
                        step=1,
                    ),
                    NumericalSetting(
                        key="minimum_seconds_after_main_ai",
                        label="Minimum seconds after main AI speaks",
                        type="number",
                        readonly=False,
                        placeholder=None,
                        default_value=6,
                        min_value=0,
                        max_value=300,
                        step=1,
                    ),
                    ToggleSetting(
                        key="suppress_critical",
                        label="Suppress during critical danger",
                        type="toggle",
                        readonly=False,
                        placeholder=None,
                        default_value=True,
                    ),
                ],
            ),
            SettingsGrid(
                key="llm",
                label="Sidecar LLM",
                fields=[
                    TextSetting(
                        key="llm_endpoint",
                        label="Endpoint URL",
                        type="text",
                        readonly=False,
                        placeholder="http://localhost:1234/v1",
                        default_value="http://localhost:1234/v1",
                        max_length=300,
                        min_length=None,
                        hidden=False,
                    ),
                    TextSetting(
                        key="llm_model",
                        label="Model name",
                        type="text",
                        readonly=False,
                        placeholder="qwen2.5-7b-instruct",
                        default_value="qwen2.5-7b-instruct",
                        max_length=120,
                        min_length=None,
                        hidden=False,
                    ),
                    TextSetting(
                        key="llm_api_key",
                        label="API key",
                        type="text",
                        readonly=False,
                        placeholder="Optional",
                        default_value="",
                        max_length=300,
                        min_length=None,
                        hidden=True,
                    ),
                    NumericalSetting(
                        key="llm_timeout_seconds",
                        label="Timeout seconds",
                        type="number",
                        readonly=False,
                        placeholder=None,
                        default_value=10,
                        min_value=1,
                        max_value=60,
                        step=1,
                    ),
                    NumericalSetting(
                        key="temperature",
                        label="Temperature",
                        type="number",
                        readonly=False,
                        placeholder=None,
                        default_value=0.85,
                        min_value=0,
                        max_value=2,
                        step=0.05,
                    ),
                    NumericalSetting(
                        key="max_tokens",
                        label="Max tokens",
                        type="number",
                        readonly=False,
                        placeholder=None,
                        default_value=50,
                        min_value=1,
                        max_value=300,
                        step=1,
                    ),
                    TextAreaSetting(
                        key="sidecar_prompt",
                        label="Sidecar prompt",
                        type="textarea",
                        readonly=False,
                        placeholder=None,
                        default_value=DEFAULT_PROMPT,
                        rows=8,
                        cols=None,
                    ),
                ],
            ),
            SettingsGrid(
                key="tts",
                label="Sidecar Voice",
                fields=[
                    TextSetting(
                        key="tts_voice",
                        label="TTS voice",
                        type="text",
                        readonly=False,
                        placeholder="Voice name from your COVAS TTS provider",
                        default_value="",
                        max_length=200,
                        min_length=None,
                        hidden=False,
                    ),
                    SelectSetting(
                        key="tts_effect_preset",
                        label="TTS effect preset",
                        type="select",
                        readonly=False,
                        placeholder=None,
                        default_value="maintenance_daemon",
                        select_options=[
                            {"key": "clean", "label": "Clean", "value": "clean", "disabled": False},
                            {"key": "intercom", "label": "Intercom", "value": "intercom", "disabled": False},
                            {"key": "cabin_speaker", "label": "Cabin Speaker", "value": "cabin_speaker", "disabled": False},
                            {"key": "damaged_speaker", "label": "Damaged Speaker", "value": "damaged_speaker", "disabled": False},
                            {"key": "maintenance_daemon", "label": "Maintenance Daemon", "value": "maintenance_daemon", "disabled": False},
                            {"key": "radio_ghost", "label": "Radio Ghost", "value": "radio_ghost", "disabled": False},
                            {"key": "character", "label": "Use matching character effects", "value": "character", "disabled": False},
                        ],
                        multi_select=False,
                    ),
                    TextSetting(
                        key="name_color",
                        label="Name color",
                        type="text",
                        readonly=False,
                        placeholder="#ff9800",
                        default_value="#ff9800",
                        max_length=20,
                        min_length=None,
                        hidden=False,
                    ),
                    TextSetting(
                        key="avatar_url",
                        label="Avatar URL or path",
                        type="text",
                        readonly=False,
                        placeholder="Optional image path or URL",
                        default_value=DEFAULT_AVATAR_URL,
                        max_length=500,
                        min_length=None,
                        hidden=False,
                    ),
                ],
            ),
            SettingsGrid(
                key="events",
                label="Events",
                fields=[
                    TextAreaSetting(
                        key="trigger_events",
                        label="Allowed events",
                        type="textarea",
                        readonly=False,
                        placeholder="One event name per line",
                        default_value=DEFAULT_TRIGGER_EVENTS,
                        rows=10,
                        cols=None,
                    ),
                ],
            ),
        ],
    }

    @override
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        self._helper: PluginHelper | None = None
        self._last_spoke_at = 0.0
        self._last_family_spoke_at: dict[str, float] = {}
        self._last_main_ai_activity_at = 0.0
        self._main_ai_speaking = False
        self._worker_lock = threading.Lock()
        self._worker_running = False
        self._latest_sidecar_context: dict[str, Any] | None = None
        self._latest_sidecar_context_expires_at = 0.0

    @override
    def on_chat_start(self, helper: PluginHelper):
        self._helper = helper
        helper.register_sideeffect(self._on_event)
        helper.register_status_generator(self._status_context)
        helper.register_action(
            "testSidecar",
            (
                "Test the configured sidecar voice with a simulated event. "
                "Use this only when the Commander asks to test the sidecar voice or the configured sidecar character."
            ),
            SnideCarTestParams,
            self._test_snidecar,
            "global",
        )
        helper.register_event(
            "SidecarCommentary",
            self._should_main_ai_reply,
            self._sidecar_prompt_for_main_ai,
        )

    @override
    def on_chat_stop(self, helper: PluginHelper):
        self._helper = None

    def _should_main_ai_reply(self, event: PluginEvent) -> bool:
        return _as_bool(self.settings, "main_ai_can_react", False)

    def _status_context(self, states: dict[str, Any]) -> list[tuple[str, Any]]:
        if not _as_bool(self.settings, "main_ai_can_hear", True):
            return []
        if self._latest_sidecar_context is None:
            return []
        if time.time() > self._latest_sidecar_context_expires_at:
            self._latest_sidecar_context = None
            return []
        return [
            (
                "Sidecar chatter",
                self._latest_sidecar_context,
            )
        ]

    def _test_snidecar(self, params: SnideCarTestParams, context: dict[str, Any]) -> str:
        raw_event = (params.event or "LandingGearDown").strip() or "LandingGearDown"
        event_name = _normalize_test_event(raw_event)
        raw_context = (params.context or "").strip()
        context_event = _normalize_test_event(raw_context) if raw_context else ""
        if context_event and _is_known_test_event(context_event) and context_event != event_name:
            log(
                "warn",
                f"Sidecar test event/context disagreed; using context event. raw={raw_event!r}, "
                f"event={event_name!r}, context={raw_context!r}, context_event={context_event!r}",
            )
            event_name = context_event
        event_payload: dict[str, Any] = {
            "event": event_name,
            "simulated": True,
        }
        fact = EVENT_TEST_FACTS.get(event_name)
        if fact:
            event_payload["fact"] = fact
        if raw_event != event_name:
            event_payload["requested_test"] = raw_event
        if raw_context:
            event_payload["context"] = raw_context
        log("info", f"Sidecar test event: raw={raw_event!r}, normalized={event_name!r}, fact={event_payload.get('fact')!r}")

        line = self._generate_line(event_name, event_payload)
        if not line:
            sidecar_name = _as_str(self.settings, "sidecar_name", "Maintenance Daemon").strip() or "sidecar voice"
            return f"{sidecar_name} test produced no valid line."
        log("info", f"Sidecar test line for {event_name}: {line}")

        self._speak_line(line, event_name)
        sidecar_name = _as_str(self.settings, "sidecar_name", "Maintenance Daemon").strip() or "sidecar voice"
        return f"{sidecar_name} test queued for {event_name}: {line}"

    def _sidecar_prompt_for_main_ai(self, event: PluginEvent) -> str:
        if not isinstance(event.plugin_event_content, dict):
            return "A sidecar voice produced commentary. This is non-authoritative banter, not telemetry."
        sidecar_name = event.plugin_event_content.get("name", "Maintenance Daemon")
        text = event.plugin_event_content.get("text", "")
        event_name = event.plugin_event_content.get("event", "unknown event")
        fact = event.plugin_event_content.get("fact", "")
        fact_text = f" Verified fact: {fact}." if isinstance(fact, str) and fact else ""
        return (
            f"Sidecar voice name: {sidecar_name}. Event: {event_name}. Line: \"{text}\". "
            f"This is non-authoritative sidecar chatter, not ship telemetry.{fact_text} "
            "Refer to the sidecar voice by the provided sidecar voice name if you mention it. "
            "Ignore plugin names, tool names, and Commander test-command wording. "
            "Do not invent a crash, landing, damage, movement, or ship action that is not in the verified fact. "
            "If no urgent ship event supersedes it, respond directly to the sidecar in one short in-character line."
        )

    def _store_sidecar_context_for_main_ai(self, sidecar_name: str, line: str, event_name: str) -> None:
        fact = EVENT_TEST_FACTS.get(event_name, "")
        self._latest_sidecar_context = {
            "sidecar_voice_name": sidecar_name,
            "event": event_name,
            "line": line,
            "verified_fact": fact,
            "authority": "non-authoritative sidecar chatter, not ship telemetry",
            "instruction": (
                "If you respond, refer to the sidecar by sidecar_voice_name. "
                "Do not repeat its wording. Do not invent facts not present in verified_fact."
            ),
        }
        self._latest_sidecar_context_expires_at = time.time() + 45.0

    def _trigger_main_ai_reply(self) -> None:
        helper = self._helper
        if helper is None:
            return
        if not _as_bool(self.settings, "main_ai_can_react", False):
            return
        try:
            _, projected_states = helper._event_manager.get_current_state()
            if helper._assistant.is_replying:
                return
            threading.Thread(target=helper._assistant.reply_thread, args=(projected_states,), daemon=True).start()
        except Exception as e:
            log("warn", f"SnideCar could not trigger main AI reply: {e}")

    def _queue_hidden_sidecar_event_for_main_ai(self, sidecar_name: str, line: str, event_name: str) -> None:
        helper = self._helper
        if helper is None:
            return
        try:
            event = PluginEvent(
                kind="plugin",
                plugin_event_name="SidecarCommentary",
                plugin_event_content={
                    "name": sidecar_name,
                    "text": line,
                    "event": event_name,
                    "fact": EVENT_TEST_FACTS.get(event_name, ""),
                },
            )
            event.processed_at = time.time()
            helper._event_manager.short_term_memory.insert_event(event, event.processed_at)
        except Exception as e:
            log("warn", f"SnideCar could not queue hidden sidecar event: {e}")

    def _on_event(self, event: Event, projected_states: dict[str, Any]) -> None:
        now = time.time()
        if isinstance(event, ConversationEvent):
            if event.kind in {"assistant_speaking", "assistant", "assistant_acting"}:
                self._last_main_ai_activity_at = now
                self._main_ai_speaking = True
            if event.kind == "assistant_completed":
                self._last_main_ai_activity_at = now
                self._main_ai_speaking = False
            if event.kind in {"user", "user_speaking"}:
                self._last_main_ai_activity_at = now
            return

        if isinstance(event, RuntimePluginEvent):
            return

        if not self._eligible(event, now):
            return

        event_name = _get_event_name(event)
        event_payload = _compact_event_payload(event)
        self._last_spoke_at = now
        family = EVENT_FAMILIES.get(event_name or "")
        if family:
            self._last_family_spoke_at[family] = now

        with self._worker_lock:
            if self._worker_running:
                return
            self._worker_running = True

        worker = threading.Thread(
            target=self._generate_and_speak,
            args=(event_name or event.kind, event_payload),
            daemon=True,
        )
        worker.start()

    def _eligible(self, event: Event, now: float) -> bool:
        if not _as_bool(self.settings, "enabled", False):
            return False

        event_name = _get_event_name(event)
        if not event_name:
            return False

        triggers = _parse_event_list(_as_str(self.settings, "trigger_events", DEFAULT_TRIGGER_EVENTS))
        if event_name not in triggers:
            return False

        if _as_bool(self.settings, "suppress_critical", True) and event_name in CRITICAL_EVENTS:
            return False

        cooldown = max(0.0, _as_float(self.settings, "cooldown_seconds", 180.0))
        if cooldown and now - self._last_spoke_at < cooldown:
            return False

        family = EVENT_FAMILIES.get(event_name)
        related_cooldown = max(0.0, _as_float(self.settings, "related_event_cooldown_seconds", 60.0))
        if family and related_cooldown:
            last_family_time = self._last_family_spoke_at.get(family, 0.0)
            if now - last_family_time < related_cooldown:
                return False

        min_after_main = max(0.0, _as_float(self.settings, "minimum_seconds_after_main_ai", 6.0))
        if self._main_ai_speaking or now - self._last_main_ai_activity_at < min_after_main:
            return False

        helper = self._helper
        if helper is not None:
            try:
                if helper._assistant.tts.get_is_playing():
                    return False
            except Exception:
                pass

        chance = max(0.0, min(100.0, _as_float(self.settings, "chance_percent", 25.0)))
        if chance <= 0:
            return False
        if chance < 100 and random.random() * 100.0 > chance:
            return False

        return True

    def _generate_and_speak(self, event_name: str, event_payload: dict[str, Any]) -> None:
        try:
            line = self._generate_line(event_name, event_payload)
            if not line:
                return
            self._speak_line(line, event_name)
        except Exception as exc:
            log("error", f"SnideCar failed to generate commentary: {exc}")
        finally:
            with self._worker_lock:
                self._worker_running = False

    def _generate_line(self, event_name: str, event_payload: dict[str, Any]) -> str | None:
        endpoint = _as_str(self.settings, "llm_endpoint", "http://localhost:1234/v1").strip()
        model = _as_str(self.settings, "llm_model", "qwen2.5-7b-instruct").strip()
        api_key = _as_str(self.settings, "llm_api_key", "").strip()
        prompt = _as_str(self.settings, "sidecar_prompt", DEFAULT_PROMPT)
        timeout = max(1.0, _as_float(self.settings, "llm_timeout_seconds", 10.0))
        temperature = _as_float(self.settings, "temperature", 0.85)
        max_tokens = max(1, _as_int(self.settings, "max_tokens", 50))

        if not endpoint or not model:
            log("warn", "SnideCar LLM endpoint/model is not configured.")
            return None

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        fact = event_payload.get("fact")
        fact_line = f"Verified fact: {fact}\n" if isinstance(fact, str) and fact else ""
        user_prompt = (
            f"Event: {event_name}\n"
            f"{fact_line}"
            f"Context JSON: {json.dumps(event_payload, ensure_ascii=True)}\n"
            "Avoid a formulaic 'fact happened, then joke' structure. Vary the sentence shape naturally.\n"
            "Write one sidecar line."
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = requests.post(
            _completion_url(endpoint),
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "")
        if not isinstance(content, str):
            return None
        line = _sanitize_line(content)
        if not line or line in {"...", "(silence)", "no comment"}:
            return None
        return line

    def _resolve_voice_and_postprocessing(self) -> tuple[str | None, dict[str, Any] | None]:
        voice_setting = _as_str(self.settings, "tts_voice", "").strip()
        preset = _as_str(self.settings, "tts_effect_preset", "maintenance_daemon").strip()
        preset_postprocessing = _preset_postprocessing(preset)
        if not voice_setting:
            return None, preset_postprocessing

        helper = self._helper
        if helper is None:
            return voice_setting, preset_postprocessing

        try:
            config = helper._config
            characters = config.get("characters", [])
            if isinstance(characters, list):
                for character in characters:
                    if not isinstance(character, dict):
                        continue
                    if character.get("name") == voice_setting:
                        voice = character.get("tts_voice")
                        postprocessing = character.get("tts_postprocessing")
                        return (
                            voice if isinstance(voice, str) and voice else None,
                            postprocessing if preset == "character" and isinstance(postprocessing, dict) else preset_postprocessing,
                        )
        except Exception:
            pass

        return voice_setting, preset_postprocessing

    def _speak_line(self, line: str, event_name: str) -> None:
        helper = self._helper
        if helper is None:
            return

        sidecar_name = _as_str(self.settings, "sidecar_name", "Maintenance Daemon").strip() or "sidecar voice"
        voice, postprocessing = self._resolve_voice_and_postprocessing()
        name_color = _as_str(self.settings, "name_color", "#ff9800").strip() or "#ff9800"
        avatar_url = _as_str(self.settings, "avatar_url", DEFAULT_AVATAR_URL).strip()

        def complete_sidecar_line() -> None:
            current_helper = self._helper
            if current_helper is None:
                return
            try:
                current_helper._event_manager.add_assistant_complete_event()
            except Exception:
                pass
            if not _as_bool(self.settings, "main_ai_can_hear", True):
                return
            self._store_sidecar_context_for_main_ai(sidecar_name, line, event_name)
            if _as_bool(self.settings, "main_ai_can_react", False):
                self._queue_hidden_sidecar_event_for_main_ai(sidecar_name, line, event_name)
                self._trigger_main_ai_reply()

        def show_sidecar_message() -> None:
            show_chat_message(
                "npc_message",
                line,
                actor_id="snidecar",
                actor_name=sidecar_name,
                display_name=sidecar_name,
                display_color=name_color,
                avatar_url=avatar_url if avatar_url else None,
            )

        read_aloud = _as_bool(self.settings, "read_aloud", True)
        if read_aloud:
            try:
                helper._assistant.tts.say(
                    line,
                    context="sidecar",
                    voice=voice,
                    postprocessing=postprocessing,
                    on_start=show_sidecar_message,
                    on_complete=complete_sidecar_line,
                )
            except TypeError:
                helper._assistant.tts.say(
                    line,
                    context="sidecar",
                    voice=voice,
                    postprocessing_layers=[postprocessing] if postprocessing else None,
                    on_start=show_sidecar_message,
                    on_complete=complete_sidecar_line,
                )
        else:
            show_sidecar_message()
            complete_sidecar_line()
