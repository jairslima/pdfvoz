"""
PDF Voz by Jair Lima — Interface de linha de comando.
"""
import os
import sys
import threading
import time

from core import clear_bookmark
from reader import Reader
from tts_engine import TTSEngine

# Teclas de controle (Windows msvcrt)
_KEY_PAUSE  = {b'p', b'P', b' '}
_KEY_NEXT   = {b'n', b'N'}
_KEY_PREV   = {b'b', b'B'}
_KEY_QUIT   = {b'q', b'Q'}
_KEY_RESTART = {b'r', b'R'}


def _print_bar(ch_idx: int, ch_title: str, p_idx: int, total_p: int, total_ch: int, paused: bool):
    status = "  [PAUSADO]" if paused else ""
    cap = f"Cap {ch_idx + 1}/{total_ch}: {ch_title[:40]}"
    prog = f"Par {p_idx + 1}/{total_p}"
    line = f"\r{cap}  |  {prog}{status}  |  P=pause  N=próx  B=ant  R=início  Q=sair   "
    print(line, end="", flush=True)


def _keyboard_loop(reader: Reader, stop_event: threading.Event):
    """Captura teclas sem Enter (Windows msvcrt)."""
    try:
        import msvcrt
    except ImportError:
        return  # Não é Windows

    while not stop_event.is_set():
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in _KEY_PAUSE:
                reader.toggle_pause()
            elif ch in _KEY_NEXT:
                reader.next_chapter()
            elif ch in _KEY_PREV:
                reader.prev_chapter()
            elif ch in _KEY_RESTART:
                reader.restart()
            elif ch in _KEY_QUIT:
                stop_event.set()
                reader.stop()
                break
        time.sleep(0.05)


def _list_chapters(reader: Reader):
    print(f"\nCapítulos em: {os.path.basename(reader.path)}\n")
    for i, ch in enumerate(reader.chapters):
        print(f"  {i + 1:3d}. {ch['title']}")
    print()


def run_cli(args):
    """Ponto de entrada do modo CLI."""
    path = args.arquivo
    if not os.path.exists(path):
        # Tentar encontrar nas pastas de projeto
        bases = [
            os.path.expanduser("~/Claude"),
            os.path.expanduser("~/Codex"),
            os.path.expanduser("~/Gemini"),
        ]
        found = None
        for base in bases:
            candidate = os.path.join(base, path)
            if os.path.exists(candidate):
                found = candidate
                break
        if found:
            path = found
        else:
            print(f"Arquivo não encontrado: {args.arquivo}")
            sys.exit(1)

    tts = TTSEngine(offline=args.offline, speed=args.velocidade)
    reader = Reader(path, tts)

    if not reader.load():
        sys.exit(1)

    if args.listar:
        _list_chapters(reader)
        return

    if args.reiniciar:
        clear_bookmark(path)
        reader.chapter_idx = 0
        reader.para_idx = 0
    elif args.capitulo is not None:
        cap = args.capitulo - 1
        reader.goto_chapter(cap)

    total_ch = len(reader.chapters)
    ch_title = reader.chapters[reader.chapter_idx]["title"] if reader.chapters else ""

    print(f"\nPDF Voz by Jair Lima")
    print(f"Arquivo : {os.path.basename(path)}")
    print(f"Voz     : {'pyttsx3 (offline)' if args.offline else 'edge-tts FranciscaNeural'}")
    print(f"Vel.    : {args.velocidade}x")
    print(f"Posição : Capítulo {reader.chapter_idx + 1}/{total_ch} — {ch_title}")
    print("-" * 60)
    print("Controles: P=Pause  N=Próximo cap.  B=Cap. anterior  R=Início  Q=Sair")
    print("-" * 60)

    # Callbacks de progresso
    _progress_cache = {"ch": 0, "p": 0, "tp": 0, "tch": 0}

    def on_progress(ch_idx, p_idx, title, total_p):
        _progress_cache.update(ch=ch_idx, p=p_idx, tp=total_p, tch=total_ch)
        _print_bar(ch_idx, title, p_idx, total_p, total_ch, reader.is_paused())

    def on_chapter_change(ch_idx, title, total_ch_):
        _progress_cache.update(ch=ch_idx, tch=total_ch_)
        print(f"\n\n>>> Capítulo {ch_idx + 1}: {title}")

    def on_finish():
        print("\n\nLeitura concluída.")
        stop_event.set()

    reader.on_progress = on_progress
    reader.on_chapter_change = on_chapter_change
    reader.on_finish = on_finish

    stop_event = threading.Event()

    # Thread de teclado
    kb_thread = threading.Thread(target=_keyboard_loop, args=(reader, stop_event), daemon=True)
    kb_thread.start()

    reader.start()

    # Aguarda encerramento
    try:
        while reader.is_running() and not stop_event.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        reader.stop()
        print("\n\nLeitura encerrada. Posição salva.")
