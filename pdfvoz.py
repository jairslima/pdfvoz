"""
PDF Voz by Jair Lima — Leitor de PDF e EPUB com Text-to-Speech.

Uso via terminal:
    pdfvoz livro.pdf
    pdfvoz livro.pdf --capitulo 3
    pdfvoz livro.pdf --listar
    pdfvoz livro.pdf --reiniciar
    pdfvoz livro.pdf --velocidade 1.5
    pdfvoz livro.pdf --offline
    pdfvoz livro.pdf --gui
    pdfvoz            (abre a interface gráfica)
"""
import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdfvoz",
        description="PDF Voz by Jair Lima — Leitor de PDF/EPUB com TTS e marcador de posição.",
    )
    p.add_argument("arquivo", nargs="?", default="", help="Arquivo PDF ou EPUB a ser lido.")
    p.add_argument("--gui", action="store_true", help="Abrir interface gráfica.")
    p.add_argument("--listar", action="store_true", help="Listar capítulos do arquivo.")
    p.add_argument("--reiniciar", action="store_true", help="Ignorar bookmark e iniciar do cap. 1.")
    p.add_argument("--capitulo", type=int, metavar="N", help="Iniciar no capítulo N.")
    p.add_argument(
        "--velocidade", type=float, default=1.0, metavar="X",
        help="Velocidade de leitura (padrão 1.0, ex: 1.5).",
    )
    p.add_argument("--offline", action="store_true", help="Usar pyttsx3 (sem internet).")
    return p


def main():
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = _build_parser()
    args = parser.parse_args()

    # Sem arquivo e sem --gui → abrir GUI
    if not args.arquivo or args.gui:
        from gui_app import run_gui
        run_gui(initial_path=args.arquivo)
        return

    from cli_app import run_cli
    run_cli(args)


if __name__ == "__main__":
    main()
