from __future__ import annotations

import logging
import threading


class TTSService:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._engine = None
        self._lock = threading.Lock()

    def _init_engine(self) -> None:
        if self._engine is None:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 170)

    def speak(self, text: str) -> None:
        if not self.enabled:
            return

        def _run() -> None:
            try:
                with self._lock:
                    self._init_engine()
                    self._engine.say(text)
                    self._engine.runAndWait()
            except Exception:
                logging.getLogger("ssi").exception("tts_failed")

        threading.Thread(target=_run, daemon=True).start()
