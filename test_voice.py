#!/usr/bin/env python3
from jarvis.voice.audio import MockAudioPlayback
from jarvis.voice.stt.faster_whisper import FasterWhisperSTT
from jarvis.voice.tts.local import PiperTTS


def test_stt():
    print("Testing FasterWhisper STT...")
    stt = FasterWhisperSTT()
    if not stt.is_available():
        print(" FasterWhisper is not available. Please install it.")
        return
    print(" FasterWhisper STT is installed and available.")
    print("Initializing model...")
    stt._get_model()
    print(" Model loaded successfully!")

def test_tts():
    print("\nTesting Piper TTS...")
    playback = MockAudioPlayback()
    tts = PiperTTS(playback)
    if not tts.is_available():
        print(" Piper TTS is not available. Please install it with: pip install piper-tts")
        return
    print(" Piper TTS is installed and available.")
    
    print("Synthesizing dummy text (mocking playback)...")
    try:
        tts.speak("Hello from Antigravity Jarvis!")
        print(" TTS playback executed.")
    except Exception as e:
        print(f" Error during playback: {e}")

if __name__ == "__main__":
    test_stt()
    test_tts()
