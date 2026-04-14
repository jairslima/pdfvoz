"""
PDF Voz by Jair Lima — Motor TTS.
edge-tts (pt-BR-FranciscaNeural) como primário, pyttsx3 como fallback offline.
"""
import asyncio
import io
import os
import subprocess
import tempfile
import threading
import time
from typing import Optional, Callable

import numpy as np
import sounddevice as sd
import soundfile as sf

VOICE_ONLINE = "pt-BR-FranciscaNeural"
SAMPLERATE_TARGET = 24000


# ---------------------------------------------------------------------------
# Conversão de velocidade
# ---------------------------------------------------------------------------

def _rate_str(speed: float) -> str:
    """1.0 → '+0%', 1.5 → '+50%', 0.8 → '-20%'."""
    pct = int(round((speed - 1.0) * 100))
    return f"+{pct}%" if pct >= 0 else f"{pct}%"


# ---------------------------------------------------------------------------
# Geração de áudio
# ---------------------------------------------------------------------------

async def _edge_tts_generate(text: str, voice: str, rate: str) -> bytes:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    mp3_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_data += chunk["data"]
    return mp3_data


def _mp3_to_array(mp3_bytes: bytes):
    """Converte bytes MP3 para numpy float32 via ffmpeg."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", "pipe:0",
            "-f", "wav", "-ar", str(SAMPLERATE_TARGET), "-ac", "1",
            "pipe:1", "-loglevel", "quiet",
        ],
        input=mp3_bytes,
        capture_output=True,
    )
    if not result.stdout:
        return None, 0
    data, sr = sf.read(io.BytesIO(result.stdout), dtype="float32")
    return data, sr


def _generate_online(text: str, speed: float):
    """Gera áudio com edge-tts. Retorna (data, samplerate) ou (None, 0)."""
    rate = _rate_str(speed)
    mp3 = asyncio.run(_edge_tts_generate(text, VOICE_ONLINE, rate))
    return _mp3_to_array(mp3)


def _generate_offline(text: str, speed: float):
    """Gera áudio com pyttsx3. Retorna (data, samplerate) ou (None, 0)."""
    import pyttsx3

    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    female = next(
        (v for v in voices if "female" in v.name.lower() or "zira" in v.name.lower()),
        None,
    )
    if female:
        engine.setProperty("voice", female.id)
    base_rate = engine.getProperty("rate")
    engine.setProperty("rate", int(base_rate * speed))

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        data, sr = sf.read(tmp_path, dtype="float32")
        return data, sr
    except Exception:
        return None, 0
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Reprodução de áudio
# ---------------------------------------------------------------------------

class AudioPlayer:
    """Reproduz numpy array com suporte a pause/resume/stop."""

    def __init__(self):
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def play(self, data: np.ndarray, samplerate: int, on_complete: Optional[Callable] = None):
        self.stop()
        self._stop.clear()
        self._pause.clear()
        self._thread = threading.Thread(
            target=self._worker, args=(data, samplerate, on_complete), daemon=True
        )
        self._thread.start()

    def pause(self):
        self._pause.set()

    def resume(self):
        self._pause.clear()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _worker(self, data: np.ndarray, samplerate: int, on_complete):
        CHUNK = samplerate // 5  # ~200 ms por chunk
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        channels = data.shape[1]
        pos = 0
        try:
            with sd.OutputStream(samplerate=samplerate, channels=channels, dtype="float32") as stream:
                while pos < len(data) and not self._stop.is_set():
                    while self._pause.is_set() and not self._stop.is_set():
                        time.sleep(0.05)
                    if self._stop.is_set():
                        break
                    chunk = data[pos : pos + CHUNK]
                    stream.write(chunk)
                    pos += CHUNK
        except Exception:
            pass
        finally:
            if on_complete and not self._stop.is_set():
                on_complete()


# ---------------------------------------------------------------------------
# Motor TTS principal
# ---------------------------------------------------------------------------

class TTSEngine:
    """
    Motor TTS unificado.
    offline=False: usa edge-tts com fallback para pyttsx3.
    offline=True: usa apenas pyttsx3.

    Pré-buffer: ao iniciar a reprodução do parágrafo N, o caller pode disparar
    prefetch(N+1) — a geração acontece em background enquanto o áudio de N toca,
    eliminando a pausa entre parágrafos.
    """

    def __init__(self, offline: bool = False, speed: float = 1.0):
        self.offline = offline
        self.speed = speed
        self._player = AudioPlayer()
        self._online_ok = True

        # Cache de pré-geração: chave = hash(text), valor = (data, sr)
        self._cache: dict[int, tuple] = {}
        self._cache_lock = threading.Lock()
        self._prefetch_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Geração de áudio
    # ------------------------------------------------------------------

    def generate_audio(self, text: str):
        """Gera (data, samplerate). Retorna (None, 0) em caso de falha."""
        if not self.offline and self._online_ok:
            try:
                data, sr = _generate_online(text, self.speed)
                if data is not None:
                    return data, sr
            except Exception:
                self._online_ok = False

        return _generate_offline(text, self.speed)

    def prefetch(self, text: str):
        """
        Inicia a geração de áudio em background para uso futuro.
        Mantém no máximo 1 entrada no cache (o próximo parágrafo).
        Silencioso: ignora erros.
        """
        key = hash(text)
        with self._cache_lock:
            if key in self._cache:
                return  # já gerado
            # Limpa entradas antigas para não acumular
            self._cache.clear()

        # Aguarda prefetch anterior se ainda rodando
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            return  # já há uma geração em andamento

        def _do():
            try:
                data, sr = self.generate_audio(text)
                if data is not None:
                    with self._cache_lock:
                        self._cache[key] = (data, sr)
            except Exception:
                pass

        self._prefetch_thread = threading.Thread(target=_do, daemon=True)
        self._prefetch_thread.start()

    def _get_cached(self, text: str):
        """Retorna áudio do cache se disponível, ou (None, 0)."""
        key = hash(text)
        with self._cache_lock:
            return self._cache.pop(key, (None, 0))

    def _wait_for_prefetch(self, text: str, stop_event, skip_event) -> tuple:
        """
        Se o prefetch está em andamento para este texto, espera ele terminar.
        Retorna (data, sr) se disponível, ou (None, 0).
        """
        key = hash(text)
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            # Espera até 10s pelo prefetch em andamento
            deadline = time.monotonic() + 10
            while self._prefetch_thread.is_alive() and time.monotonic() < deadline:
                if (stop_event and stop_event.is_set()) or (skip_event and skip_event.is_set()):
                    return None, 0
                time.sleep(0.05)

        with self._cache_lock:
            return self._cache.pop(key, (None, 0))

    # ------------------------------------------------------------------
    # Reprodução síncrona
    # ------------------------------------------------------------------

    def speak_sync(
        self,
        text: str,
        stop_event: Optional[threading.Event] = None,
        skip_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None,
        on_playing: Optional[Callable] = None,
    ):
        """
        Gera áudio e toca de forma síncrona.
        Respeita stop_event (sair), skip_event (pular) e pause_event (pausar).

        on_playing: chamado logo após o início da reprodução — use para
                    disparar prefetch do próximo parágrafo enquanto este toca.
        """
        # 1. Verificar cache (pré-buffer do parágrafo anterior)
        data, sr = self._get_cached(text)

        if data is None:
            # 2. Verificar se prefetch está em andamento para este texto
            data, sr = self._wait_for_prefetch(text, stop_event, skip_event)

        if data is None:
            # 3. Gerar agora (fallback síncrono com suporte a abort)
            result = [None, 0]
            gen_done = threading.Event()

            def _generate():
                result[0], result[1] = self.generate_audio(text)
                gen_done.set()

            gen_thread = threading.Thread(target=_generate, daemon=True)
            gen_thread.start()

            while not gen_done.is_set():
                if (stop_event and stop_event.is_set()) or (skip_event and skip_event.is_set()):
                    return
                time.sleep(0.05)

            data, sr = result[0], result[1]

        if data is None:
            return

        if (stop_event and stop_event.is_set()) or (skip_event and skip_event.is_set()):
            return

        # 4. Iniciar reprodução
        done = threading.Event()
        self._player.play(data, sr, on_complete=done.set)

        # 5. Disparar callback on_playing (para prefetch do próximo parágrafo)
        if on_playing:
            on_playing()

        # 6. Aguardar fim respeitando eventos
        while not done.is_set():
            if (stop_event and stop_event.is_set()) or (skip_event and skip_event.is_set()):
                self._player.stop()
                return
            if pause_event and pause_event.is_set():
                self._player.pause()
                while pause_event.is_set():
                    if (stop_event and stop_event.is_set()) or (skip_event and skip_event.is_set()):
                        self._player.stop()
                        return
                    time.sleep(0.05)
                self._player.resume()
            time.sleep(0.05)

    def pause(self):
        self._player.pause()

    def resume(self):
        self._player.resume()

    def stop(self):
        self._player.stop()
        # Limpa cache ao parar (evita reproduzir áudio obsoleto após skip)
        with self._cache_lock:
            self._cache.clear()
