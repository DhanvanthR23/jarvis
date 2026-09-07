# G24 Voice Interface: Completion Documentation

## STT & TTS Backend Note
The current validated STT/TTS backend is Vosk (small model) and Piper. This was validated by the G24.3 resource benchmark on the target hardware (484 MB peak RAM, 851ms transcription latency per 3s audio).

**CRITICAL:** This specific backend choice (Vosk + Piper) is *not* a permanent architectural commitment. The `SpeechToText` and `TextToSpeech` abstractions exist precisely so that this backend can be swapped out later without altering the `JarvisController` or `VoiceRuntime`. Swapping the backend in the future does not violate any frozen architectural decisions made in G24.

## Confirmation Confidence Threshold
The 0.8 STT minimum confidence threshold applied to explicit voice approvals (`yes jarvis confirm`) is an empirical/operational tuning value chosen from testing. 

**CRITICAL:** This threshold is *not* a security guarantee. It does *not* authenticate the speaker (per Invariant M: Jarvis cannot authenticate users via voice). It must never be described or relied upon as proof of speaker identity. It is solely an operational filter to prevent garbled background noise from accidentally triggering a confirmation.

Note: This 0.8 threshold is *only* applied during the explicit approval confirmation flow in `jarvis/voice/confirmation.py`. It is *not* applied to ordinary command interpretation (e.g., "what time is it?"), which relies entirely on the agent backend to interpret or reject ambiguous speech.

## Output Security Filter: Pattern Layer Test Coverage & Limitations

The secondary (pattern-detection) layer of the `OutputSecurityFilter` exists to catch cases where AGY transcribes secrets into freeform prose after original metadata/provenance tags are lost. 

**Tested Coverage:**
- The pattern layer is confirmed to catch secrets reproduced in recognizable literal format (e.g. `AKIA1234567890123456`), even when embedded directly in unrelated, paraphrased carrier prose.
- It also correctly detects literal secrets even when slightly reformatted or split across spacing (e.g. `A K I A 1 2 3...`).

**Explicit Limitations (Semantic-Description Gap):**
- The regex layer is **not** confirmed to catch purely semantic or descriptive leakage.
- Cases where AGY conveys the existence, type, or partial substance of a secret without outputting any literal, regex-matchable substring (e.g. "The key I found starts with A-K-I-A followed by a string of numbers") will slip past the filter.
- This semantic-description gap is an explicit, documented limitation of the current implementation, not a solved problem.
- **Suggested Direction:** Closing this gap robustly likely requires constraining what AGY is permitted to "see" of `SECRET`-tagged tool results upstream (e.g., redacting them from the agent's context window entirely before it generates prose), rather than exclusively relying on downstream output filtering after the fact.
