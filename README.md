# SnideCar

SnideCar is a COVAS:NEXT plugin that adds an optional second AI voice: a small sidecar commentator that occasionally reacts to selected ship events.

The main COVAS character stays primary. SnideCar is entertainment chatter, not ship telemetry, not a copilot, and not a tool user.

## Features

- Watches selected COVAS:NEXT ship events.
- Sends a tiny prompt to an OpenAI-compatible chat completion endpoint.
- Speaks the returned line through COVAS:NEXT TTS.
- Supports its own display name, color, avatar, voice, and TTS effect preset.
- Can optionally dispatch `SidecarCommentary` so the main AI can hear and react.
- Includes a built-in SVG avatar at `SnideCarPlugin/assets/snidecar_daemon.svg`.
- Includes a `testSidecar` action for simulated event testing.

## Installation

1. Copy the `SnideCarPlugin` folder into your COVAS:NEXT plugins directory.
2. Start or restart COVAS:NEXT.
3. Open plugin settings and enable SnideCar.
4. Configure the sidecar LLM endpoint, model, prompt, voice, and trigger events.

Typical plugin directory:

```text
%APPDATA%\com.covas-next.ui\plugins\SnideCarPlugin
```

## LLM Setup

SnideCar expects an OpenAI-compatible `/v1/chat/completions` endpoint.

Example local endpoint:

```text
http://localhost:1234/v1
```

Example local model name:

```text
qwen2.5-7b-instruct
```

Example hosted endpoint:

```text
https://api.deepinfra.com/v1/openai
```

If your provider requires an API key, enter it in the plugin settings. The API key field defaults to empty.

## TTS Setup

SnideCar uses the active COVAS:NEXT TTS system. It does not require a separate TTS server setting in the plugin.

You can configure:

- TTS voice
- name color
- avatar path or URL
- TTS effect preset

If `TTS voice` matches an existing COVAS:NEXT character name and the preset is set to `Use matching character effects`, SnideCar can reuse that character's configured voice/effects.

## Included Effect Presets

- Clean
- Intercom
- Cabin Speaker
- Damaged Speaker
- Maintenance Daemon
- Radio Ghost
- Use matching character effects

## Main AI Interaction

SnideCar can optionally let the main AI hear its commentary.

When enabled, SnideCar dispatches a `SidecarCommentary` plugin event containing:

- sidecar voice name
- event name
- spoken line
- verified event fact, when available

The main AI is told that this is non-authoritative sidecar chatter, not ship telemetry.

## Safety Notes

SnideCar is designed to be optional and low-authority.

- It does not call ship tools.
- It does not answer Commander commands.
- It should not replace the main COVAS AI.
- It should not be treated as factual telemetry by the main AI.
- It can be disabled, cooled down, randomized, or restricted to specific events.

## Packaging

Package the `SnideCarPlugin` folder. Do not include your COVAS:NEXT `config.json`, logs, cache files, or `__pycache__`.
