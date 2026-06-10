# SnideCar Concept

SnideCar is a standalone COVAS:NEXT plugin concept that adds a secondary AI voice: a small, configurable sidecar commentator that occasionally reacts to ship events with short zingers, mutters, warnings, or insults.

The main COVAS character remains primary. SnideCar is not a second assistant, not a copilot, and not a tool user. It is an entertainment/commentary layer: a mouthy ship subroutine, maintenance daemon, backseat AI, or other optional counterpart.

## Core Idea

SnideCar watches selected COVAS events, sends a tiny prompt to a configurable LLM endpoint, speaks the returned line using COVAS TTS with its own configured voice/effects, and optionally dispatches a plugin event so the main AI can hear and react.

Example:

Event: LandingGearDown

SnideCar: "Excellent. Expensive knees deployed into traffic again."

Cassia, if allowed to react: "Ignore the dramatic tin can, Boss. Gear's down."

## Design Goals

- Run as a standalone COVAS:NEXT plugin.
- Avoid modifying COVAS:NEXT core code during prototype.
- Use configurable OpenAI-compatible LLM endpoints.
- Use COVAS internal TTS rather than custom audio playback.
- Support separate sidecar voice and TTS effects.
- Keep output short, rare, and non-authoritative.
- Let the main AI hear/react only when enabled.
- Prevent runaway banter loops.
- Keep cost low by sending tiny prompts to a small model.

## Non-Goals

- SnideCar should not call ship tools.
- SnideCar should not answer Commander commands.
- SnideCar should not replace the main COVAS AI.
- SnideCar should not write long-term memory as fact.
- SnideCar should not receive full COVAS context.
- SnideCar should not speak during critical moments by default.

## Proposed Runtime Flow

1. COVAS receives a game/status/conversation event.
2. SnideCar observes the event through `PluginHelper.register_sideeffect`.
3. SnideCar checks whether the event is eligible.
4. SnideCar checks cooldowns, chance, danger suppression, and speaking state.
5. SnideCar builds a tiny prompt from the event and minimal projected state.
6. SnideCar calls its configured LLM endpoint.
7. SnideCar validates and trims the returned line.
8. SnideCar speaks through COVAS TTS with its configured voice/effects.
9. SnideCar optionally dispatches a `PluginEvent` so the main AI can hear it.
10. The main AI may react once if the setting allows it.

## Preferred Audio Path

Use COVAS TTS internally:

```python
helper._assistant.tts.say(
    line,
    voice=sidecar_voice,
    postprocessing=sidecar_postprocessing,
)
```

This mirrors the EDCoPilot commentary branch pattern and avoids separate audio playback, output-device handling, and queue conflicts.

The private `_assistant` access is acceptable for a prototype. If the concept is upstreamed later, a public helper like `helper.say(...)` or `helper.emit_npc_message(...)` would be cleaner.

## Cassia/Main AI Interaction

SnideCar can optionally dispatch a plugin event:

```text
Sidecar commentary from Maintenance Daemon:
"Landing gear deployed. Expensive knees extended again."

This is non-authoritative banter, not ship telemetry.
```

Rules:

- Main AI may hear SnideCar if enabled.
- Main AI may reply once if enabled.
- Main AI must not treat SnideCar claims as telemetry.
- SnideCar output should not trigger another SnideCar output.
- SnideCar should not respond to the main AI unless a future "conversation mode" explicitly allows it.

## Initial Settings

General:

- Enabled
- Sidecar name
- Sidecar prompt
- Read commentary aloud
- Let main AI hear sidecar
- Let main AI immediately react
- Cooldown seconds
- Chance to comment percent
- Minimum seconds after main AI speech
- Suppress during critical danger

LLM:

- Endpoint URL
- Model name
- API key
- Timeout seconds
- Temperature
- Max tokens

TTS:

- Voice
- Optional name color
- Optional avatar URL
- Optional postprocessing/effects preset

Events:

- Allowed event list or categories
- Blocked event list

## First Prototype Defaults

Name: Maintenance Daemon

Endpoint: `http://localhost:1234/v1`

Model: `qwen2.5-7b-instruct`

Prompt:

```text
You are Maintenance Daemon, a bitter ship maintenance subroutine in Elite Dangerous.
Reply with exactly one short sentence under fifteen words.
No questions. No advice. No stage directions.
Do not invent facts. Comment only on the provided event.
Sound annoyed, dry, and mechanical.
```

Prototype triggers:

- LandingGearDown
- LandingGearUp
- DockingDenied
- DockingGranted
- ProspectedAsteroid
- MiningRefined
- HeatWarning
- EjectCargo
- Limpet-related events if available

Prototype suppressions:

- Commander speech
- User speaking
- Main AI speaking
- Hull critical
- Shields down
- UnderAttack
- CombatEntered
- Tool execution/results unless explicitly enabled later

Cooldown:

- Start with 180 seconds.

Chance:

- Start with 25 percent.

Main AI reaction:

- Default off.

## Known Risks

Audio clutter:

SnideCar can become annoying fast. Cooldowns and suppression are mandatory.

Context poisoning:

If SnideCar lines enter the main AI prompt, they must be marked non-authoritative.

Runaway banter:

SnideCar must not answer its own events or create loops with the main AI.

Private API usage:

Using `helper._assistant.tts.say(...)` is pragmatic but not formally public.

Model looseness:

Small local models can be funny but may invent facts. Keep prompts tiny and validate output.

Timing:

The joke must arrive quickly. A small local or inexpensive hosted model is usually a better fit than a large, slow reasoning model.

## Open Questions

- Should SnideCar show in chat/overlay as a plugin event, NPC message, or not at all?
- Should SnideCar use COVAS TTS queue only, or should it optionally use external TTS later?
- Should TTS postprocessing mirror character settings exactly or use simplified presets?
- Should event eligibility use explicit event names first, then categories later?
- Should plugin settings support multiple sidecar personalities in one plugin?
- Should Cassia/main AI reaction be immediate, delayed, or only visible as context for the next normal reply?

## Current Prototype Notes

SnideCar now displays its spoken line as an `npc_message` chat/overlay message when speech starts. It uses the sidecar name as display name, the configured name color, and an optional avatar URL/path.

SnideCar speaks through the COVAS TTS queue and can apply one of several built-in effect presets:

- Clean
- Intercom
- Damaged Speaker
- Maintenance Daemon
- Radio Ghost
- Use matching character effects

If `TTS voice` matches an existing COVAS character name and the preset is `Use matching character effects`, SnideCar reuses that character's voice and postprocessing. Otherwise the configured voice is passed directly to the active COVAS TTS provider.

## Implementation Chunks

1. Scaffold plugin folder and manifest. Done.
2. Add settings definition. Done.
3. Add OpenAI-compatible LLM client. Done.
4. Add event sideeffect with trigger filtering. Done.
5. Add cooldown/chance/speaking-state guard. Done.
6. Add COVAS TTS speech call. Done.
7. Add optional plugin event dispatch for main AI awareness. Done.
8. Add logs and safe failure handling. First pass done.
9. Test with fake events. Next.
10. Test in live COVAS with a narrow trigger list. Pending.
