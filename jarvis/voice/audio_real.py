import pyaudio
import threading
import sys
import os
import contextlib
from jarvis.voice.audio import AudioCapture, AudioPlayback, AudioChunk

@contextlib.contextmanager
def suppress_alsa_warnings():
    """Redirects C-level stderr to /dev/null to silence ALSA/JACK warnings."""
    try:
        stderr_fd = sys.stderr.fileno()
        saved_stderr_fd = os.dup(stderr_fd)
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, stderr_fd)
        yield
        os.dup2(saved_stderr_fd, stderr_fd)
        os.close(devnull_fd)
        os.close(saved_stderr_fd)
    except Exception:
        yield

class PyAudioCapture(AudioCapture):
    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels
        with suppress_alsa_warnings():
            self.p = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self._recording = False
        self.thread = None

    def is_available(self):
        return True

    def start(self):
        self.frames = []
        self._recording = True
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=self.channels,
                                  rate=self.sample_rate,
                                  input=True,
                                  frames_per_buffer=1024)
        def _record():
            while self._recording:
                try:
                    data = self.stream.read(1024, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception:
                    break
        self.thread = threading.Thread(target=_record)
        self.thread.start()

    def stop(self) -> AudioChunk:
        self._recording = False
        if self.thread and self.thread.is_alive():
            self.thread.join()
        
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            
        data = b''.join(self.frames)
        return AudioChunk(data=data, sample_rate=self.sample_rate, channels=self.channels)

class PyAudioPlayback(AudioPlayback):
    def __init__(self):
        with suppress_alsa_warnings():
            self.p = pyaudio.PyAudio()
        self.stream = None

    def is_available(self):
        return True

    def play(self, audio: bytes):
        import wave
        import io
        with wave.open(io.BytesIO(audio), 'rb') as wf:
            self.stream = self.p.open(format=self.p.get_format_from_width(wf.getsampwidth()),
                                      channels=wf.getnchannels(),
                                      rate=wf.getframerate(),
                                      output=True)
            data = wf.readframes(1024)
            while data:
                self.stream.write(data)
                data = wf.readframes(1024)
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
