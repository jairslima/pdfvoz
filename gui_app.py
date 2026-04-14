"""
PDF Voz by Jair Lima — Interface gráfica Tkinter.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import clear_bookmark
from reader import Reader
from tts_engine import TTSEngine

# ---------------------------------------------------------------------------
# Paleta de cores (tema escuro)
# ---------------------------------------------------------------------------
BG        = "#1e1e2e"
BG2       = "#2a2a3e"
BG3       = "#313149"
FG        = "#cdd6f4"
FG_DIM    = "#6c7086"
ACCENT    = "#89b4fa"
ACCENT2   = "#cba6f7"
GREEN     = "#a6e3a1"
RED       = "#f38ba8"
YELLOW    = "#f9e2af"
FONT_MAIN = ("Segoe UI", 11)
FONT_MONO = ("Consolas", 10)
FONT_BIG  = ("Segoe UI", 13, "bold")
FONT_SM   = ("Segoe UI", 9)


class PdfVozApp(tk.Tk):
    """Janela principal do PDF Voz by Jair Lima."""

    def __init__(self, initial_path: str = ""):
        super().__init__()
        self.title("PDF Voz by Jair Lima")
        self.configure(bg=BG)
        self.geometry("820x600")
        self.minsize(700, 500)

        self.reader: Reader | None = None
        self.tts: TTSEngine | None = None
        self._speed = tk.DoubleVar(value=1.0)
        self._offline = tk.BooleanVar(value=False)
        self._current_file = tk.StringVar(value="")
        self._status = tk.StringVar(value="Abra um arquivo para iniciar.")
        self._chapter_var = tk.StringVar()
        self._is_playing = False

        self._build_ui()

        if initial_path and os.path.exists(initial_path):
            self.after(200, lambda: self._open_file(initial_path))

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # === Cabeçalho ===
        header = tk.Frame(self, bg=BG2, pady=8)
        header.pack(fill="x")

        tk.Label(
            header, text="PDF Voz by Jair Lima",
            font=FONT_BIG, bg=BG2, fg=ACCENT,
        ).pack(side="left", padx=16)

        # Modo offline
        tk.Checkbutton(
            header, text="Offline (pyttsx3)",
            variable=self._offline, bg=BG2, fg=FG_DIM,
            activebackground=BG2, activeforeground=FG,
            selectcolor=BG3, font=FONT_SM,
        ).pack(side="right", padx=12)

        # === Barra de arquivo ===
        file_bar = tk.Frame(self, bg=BG3, pady=6)
        file_bar.pack(fill="x")

        tk.Button(
            file_bar, text="Abrir PDF/EPUB",
            command=self._browse_file,
            bg=ACCENT, fg=BG, font=FONT_MAIN,
            relief="flat", padx=12, cursor="hand2",
        ).pack(side="left", padx=10)

        tk.Label(
            file_bar, textvariable=self._current_file,
            bg=BG3, fg=FG, font=FONT_MONO, anchor="w",
        ).pack(side="left", padx=4, fill="x", expand=True)

        # === Seletor de capítulo ===
        ch_bar = tk.Frame(self, bg=BG2, pady=5)
        ch_bar.pack(fill="x")

        tk.Label(ch_bar, text="Capítulo:", bg=BG2, fg=FG_DIM, font=FONT_SM).pack(side="left", padx=10)

        self._chapter_combo = ttk.Combobox(
            ch_bar, textvariable=self._chapter_var,
            state="readonly", font=FONT_SM, width=50,
        )
        self._chapter_combo.pack(side="left", padx=4)
        self._chapter_combo.bind("<<ComboboxSelected>>", self._on_chapter_selected)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=BG3, background=BG3, foreground=FG, arrowcolor=ACCENT)

        # === Área de texto ===
        txt_frame = tk.Frame(self, bg=BG, pady=4)
        txt_frame.pack(fill="both", expand=True, padx=12)

        self._text = tk.Text(
            txt_frame, bg=BG2, fg=FG, font=FONT_MAIN,
            relief="flat", wrap="word", state="disabled",
            padx=12, pady=12, selectbackground=ACCENT2,
        )
        scrollbar = tk.Scrollbar(txt_frame, command=self._text.yview, bg=BG3)
        self._text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._text.pack(side="left", fill="both", expand=True)

        self._text.tag_configure("current", background=BG3, foreground=YELLOW)

        # === Barra de progresso ===
        prog_frame = tk.Frame(self, bg=BG, padx=12, pady=2)
        prog_frame.pack(fill="x")

        self._progress_label = tk.Label(
            prog_frame, text="", bg=BG, fg=FG_DIM, font=FONT_SM, anchor="w",
        )
        self._progress_label.pack(side="left")

        self._progress_bar = ttk.Progressbar(prog_frame, length=300, mode="determinate")
        style.configure("TProgressbar", troughcolor=BG3, background=ACCENT)
        self._progress_bar.pack(side="right", padx=4)

        # === Controles de velocidade ===
        speed_frame = tk.Frame(self, bg=BG2, pady=6)
        speed_frame.pack(fill="x")

        tk.Label(speed_frame, text="Velocidade:", bg=BG2, fg=FG_DIM, font=FONT_SM).pack(side="left", padx=12)

        self._speed_label = tk.Label(speed_frame, text="1.0x", bg=BG2, fg=ACCENT, font=FONT_SM, width=5)
        self._speed_label.pack(side="left")

        speed_slider = tk.Scale(
            speed_frame, variable=self._speed,
            from_=0.5, to=3.0, resolution=0.1,
            orient="horizontal", length=200,
            bg=BG2, fg=FG, troughcolor=BG3,
            highlightthickness=0, sliderrelief="flat",
            command=self._on_speed_change,
        )
        speed_slider.pack(side="left", padx=4)

        # === Botões de controle ===
        btn_frame = tk.Frame(self, bg=BG2, pady=8)
        btn_frame.pack(fill="x")

        btn_cfg = dict(font=("Segoe UI", 14), relief="flat", padx=14, pady=4, cursor="hand2")

        tk.Button(btn_frame, text="|◄", command=self._btn_restart,
                  bg=BG3, fg=FG, **btn_cfg).pack(side="left", padx=6)
        tk.Button(btn_frame, text="◄", command=self._btn_prev,
                  bg=BG3, fg=FG, **btn_cfg).pack(side="left", padx=4)

        self._play_btn = tk.Button(
            btn_frame, text="▶", command=self._btn_play_pause,
            bg=GREEN, fg=BG, font=("Segoe UI", 16, "bold"),
            relief="flat", padx=18, pady=4, cursor="hand2",
        )
        self._play_btn.pack(side="left", padx=8)

        tk.Button(btn_frame, text="►", command=self._btn_next,
                  bg=BG3, fg=FG, **btn_cfg).pack(side="left", padx=4)
        tk.Button(btn_frame, text="■", command=self._btn_stop,
                  bg=RED, fg=BG, **btn_cfg).pack(side="left", padx=6)

        # Status
        self._status_label = tk.Label(
            btn_frame, textvariable=self._status,
            bg=BG2, fg=FG_DIM, font=FONT_SM, anchor="w",
        )
        self._status_label.pack(side="right", padx=12)

    # ------------------------------------------------------------------
    # Abertura de arquivo
    # ------------------------------------------------------------------

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Selecionar arquivo",
            filetypes=[("PDF e EPUB", "*.pdf *.epub"), ("PDF", "*.pdf"), ("EPUB", "*.epub")],
        )
        if path:
            self._open_file(path)

    def _open_file(self, path: str):
        if self.reader and self.reader.is_running():
            self.reader.stop()

        self._current_file.set(os.path.basename(path))
        self._status.set("Carregando arquivo...")
        self.update()

        tts = TTSEngine(offline=self._offline.get(), speed=self._speed.get())
        reader = Reader(path, tts)

        if not reader.load():
            messagebox.showerror("Erro", "Não foi possível abrir o arquivo.")
            self._status.set("Erro ao abrir arquivo.")
            return

        self.tts = tts
        self.reader = reader
        self._is_playing = False
        self._play_btn.configure(text="▶", bg=GREEN)

        # Conecta callbacks
        reader.on_progress      = self._on_progress
        reader.on_chapter_change = self._on_chapter_change
        reader.on_finish        = self._on_finish
        reader.on_error         = self._on_error

        # Popula dropdown de capítulos
        titles = [f"{i+1}. {ch['title']}" for i, ch in enumerate(reader.chapters)]
        self._chapter_combo.configure(values=titles)
        self._update_chapter_combo()

        # Mostra posição inicial
        ch_title = reader.chapters[reader.chapter_idx]["title"]
        self._status.set(
            f"Pronto. Cap. {reader.chapter_idx + 1}: {ch_title} | Par. {reader.para_idx + 1}"
        )
        self._show_chapter_text(reader.chapter_idx, reader.para_idx)

    # ------------------------------------------------------------------
    # Callbacks do Reader (vêm do thread de leitura — usar after())
    # ------------------------------------------------------------------

    def _on_progress(self, ch_idx: int, p_idx: int, ch_title: str, total_p: int):
        self.after(0, lambda: self._update_progress(ch_idx, p_idx, ch_title, total_p))

    def _on_chapter_change(self, ch_idx: int, title: str, total_ch: int):
        self.after(0, lambda: self._update_chapter_ui(ch_idx, title, total_ch))

    def _on_finish(self):
        self.after(0, self._on_reading_finished)

    def _on_error(self, msg: str):
        self.after(0, lambda: messagebox.showerror("Erro", msg))

    def _update_progress(self, ch_idx, p_idx, ch_title, total_p):
        if not self.reader:
            return
        total_ch = len(self.reader.chapters)
        self._progress_label.configure(
            text=f"Cap {ch_idx+1}/{total_ch}  |  Par {p_idx+1}/{total_p}"
        )
        pct = int((p_idx / max(1, total_p)) * 100)
        self._progress_bar["value"] = pct
        self._status.set(f"Lendo: {ch_title[:50]}")
        self._highlight_paragraph(p_idx)

    def _update_chapter_ui(self, ch_idx, title, total_ch):
        self._update_chapter_combo()
        self._show_chapter_text(ch_idx, 0)
        self._progress_bar["value"] = 0

    def _on_reading_finished(self):
        self._is_playing = False
        self._play_btn.configure(text="▶", bg=GREEN)
        self._status.set("Leitura concluída.")

    # ------------------------------------------------------------------
    # Atualização de texto / destaque
    # ------------------------------------------------------------------

    def _show_chapter_text(self, ch_idx: int, active_para: int = 0):
        if not self.reader or ch_idx >= len(self.reader.chapters):
            return
        paras = self.reader.chapters[ch_idx]["paragraphs"]
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        for i, para in enumerate(paras):
            self._text.insert("end", para + "\n\n", f"para_{i}")
        self._text.configure(state="disabled")
        self._highlight_paragraph(active_para)

    def _highlight_paragraph(self, p_idx: int):
        self._text.configure(state="normal")
        self._text.tag_remove("current", "1.0", "end")
        tag = f"para_{p_idx}"
        ranges = self._text.tag_ranges(tag)
        if ranges:
            self._text.tag_add("current", ranges[0], ranges[1])
            self._text.see(ranges[0])
        self._text.configure(state="disabled")

    def _update_chapter_combo(self):
        if not self.reader:
            return
        idx = self.reader.chapter_idx
        titles = [f"{i+1}. {ch['title']}" for i, ch in enumerate(self.reader.chapters)]
        self._chapter_combo.configure(values=titles)
        if 0 <= idx < len(titles):
            self._chapter_combo.current(idx)

    # ------------------------------------------------------------------
    # Handlers de botões
    # ------------------------------------------------------------------

    def _btn_play_pause(self):
        if not self.reader:
            self._browse_file()
            return

        if not self._is_playing:
            # Iniciar leitura
            self._is_playing = True
            self._play_btn.configure(text="⏸", bg=YELLOW)
            self.reader.resume()
            if not self.reader.is_running():
                self.reader.start()
        else:
            if self.reader.is_paused():
                self.reader.resume()
                self._play_btn.configure(text="⏸", bg=YELLOW)
            else:
                self.reader.pause()
                self._play_btn.configure(text="▶", bg=GREEN)

    def _btn_stop(self):
        if self.reader:
            self.reader.stop()
        self._is_playing = False
        self._play_btn.configure(text="▶", bg=GREEN)
        self._status.set("Parado. Posição salva.")

    def _btn_next(self):
        if self.reader:
            self.reader.next_chapter()
            self._update_chapter_combo()
            self._show_chapter_text(self.reader.chapter_idx)

    def _btn_prev(self):
        if self.reader:
            self.reader.prev_chapter()
            self._update_chapter_combo()
            self._show_chapter_text(self.reader.chapter_idx)

    def _btn_restart(self):
        if self.reader:
            self.reader.restart()
            self._update_chapter_combo()
            self._show_chapter_text(0)

    def _on_chapter_selected(self, _event=None):
        if not self.reader:
            return
        idx = self._chapter_combo.current()
        was_playing = self._is_playing and not self.reader.is_paused()
        self.reader.goto_chapter(idx)
        self._show_chapter_text(idx)
        if was_playing and not self.reader.is_running():
            self.reader.start()

    def _on_speed_change(self, value):
        spd = float(value)
        self._speed_label.configure(text=f"{spd:.1f}x")
        if self.tts:
            self.tts.speed = spd

    # ------------------------------------------------------------------
    # Protocolo de fechamento
    # ------------------------------------------------------------------

    def destroy(self):
        if self.reader:
            self.reader.stop()
        super().destroy()


def run_gui(initial_path: str = ""):
    app = PdfVozApp(initial_path=initial_path)
    app.mainloop()
