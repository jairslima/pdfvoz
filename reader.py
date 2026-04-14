"""
PDF Voz by Jair Lima — Loop de leitura compartilhado entre CLI e GUI.
"""
import threading
import time
from typing import Optional, Callable

from core import save_bookmark, load_file, get_bookmark
from tts_engine import TTSEngine


class Reader:
    """
    Controla o loop de leitura: carrega arquivo, navega capítulos,
    chama TTS e salva bookmark.

    Callbacks (chamados do thread de leitura):
        on_progress(ch_idx, para_idx, ch_title, total_paras)
        on_chapter_change(ch_idx, title, total_chapters)
        on_finish()
        on_error(msg)
    """

    def __init__(self, path: str, tts: TTSEngine):
        self.path = path
        self.tts = tts
        self.chapters: list[dict] = []

        self.chapter_idx = 0
        self.para_idx = 0

        self._stop = threading.Event()
        self._pause = threading.Event()
        self._skip = threading.Event()   # pular parágrafo atual (para next/prev chapter)
        self._thread: Optional[threading.Thread] = None

        # Callbacks para a UI
        self.on_progress: Optional[Callable] = None
        self.on_chapter_change: Optional[Callable] = None
        self.on_finish: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Carregamento
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Carrega o arquivo e restaura bookmark se existir. Retorna True se OK."""
        try:
            self.chapters = load_file(self.path)
        except Exception as e:
            if self.on_error:
                self.on_error(f"Erro ao abrir arquivo: {e}")
            return False

        bm = get_bookmark(self.path)
        if bm:
            self.chapter_idx = min(bm.get("chapter", 0), len(self.chapters) - 1)
            self.para_idx = bm.get("paragraph", 0)
        else:
            self.chapter_idx = 0
            self.para_idx = 0

        return True

    # ------------------------------------------------------------------
    # Controles de navegação
    # ------------------------------------------------------------------

    def next_chapter(self):
        if self.chapter_idx < len(self.chapters) - 1:
            self.chapter_idx += 1
            self.para_idx = 0
            self._skip.set()
            self.tts.stop()

    def prev_chapter(self):
        if self.chapter_idx > 0:
            self.chapter_idx -= 1
            self.para_idx = 0
            self._skip.set()
            self.tts.stop()

    def goto_chapter(self, idx: int):
        idx = max(0, min(idx, len(self.chapters) - 1))
        self.chapter_idx = idx
        self.para_idx = 0
        self._skip.set()
        self.tts.stop()

    def restart(self):
        self.chapter_idx = 0
        self.para_idx = 0
        self._skip.set()
        self.tts.stop()

    # ------------------------------------------------------------------
    # Pause / Resume
    # ------------------------------------------------------------------

    def pause(self):
        self._pause.set()
        self.tts.pause()

    def resume(self):
        self._pause.clear()
        self.tts.resume()

    def toggle_pause(self):
        if self._pause.is_set():
            self.resume()
        else:
            self.pause()

    def is_paused(self) -> bool:
        return self._pause.is_set()

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def start(self):
        """Inicia (ou reinicia) o loop de leitura em thread separada."""
        if self.is_running():
            return
        self._stop.clear()
        self._skip.clear()
        self._pause.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Para leitura completamente e aguarda a thread encerrar."""
        self._stop.set()
        self._skip.set()     # desbloqueia qualquer espera de skip
        self.tts.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Loop principal de leitura
    # ------------------------------------------------------------------

    def _loop(self):
        while not self._stop.is_set():
            self._skip.clear()

            ch_idx = self.chapter_idx
            if ch_idx >= len(self.chapters):
                break

            chapter = self.chapters[ch_idx]
            paras = chapter["paragraphs"]
            total_ch = len(self.chapters)

            if self.on_chapter_change:
                self.on_chapter_change(ch_idx, chapter["title"], total_ch)

            p_idx = self.para_idx

            while not self._stop.is_set() and not self._skip.is_set() and p_idx < len(paras):
                # Espera pause (entre parágrafos)
                while self._pause.is_set() and not self._stop.is_set() and not self._skip.is_set():
                    time.sleep(0.1)

                if self._stop.is_set() or self._skip.is_set():
                    break

                self.para_idx = p_idx
                save_bookmark(self.path, ch_idx, p_idx)

                if self.on_progress:
                    self.on_progress(ch_idx, p_idx, chapter["title"], len(paras))

                self.tts.speak_sync(
                    paras[p_idx],
                    stop_event=self._stop,
                    skip_event=self._skip,
                    pause_event=self._pause,
                )

                if self._stop.is_set() or self._skip.is_set():
                    break

                p_idx += 1
                self.para_idx = p_idx

            # Capítulo concluído naturalmente (sem skip ou stop)
            if not self._stop.is_set() and not self._skip.is_set():
                if ch_idx + 1 < len(self.chapters):
                    self.chapter_idx = ch_idx + 1
                    self.para_idx = 0
                else:
                    # Fim do livro
                    break

        if not self._stop.is_set() and self.on_finish:
            self.on_finish()
