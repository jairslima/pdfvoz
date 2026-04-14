# PDF Voz by Jair Lima

## Descrição
Leitor de PDF e EPUB com Text-to-Speech. Uso primário via terminal, com interface gráfica disponível. Diferencial: marcador de posição automático — retoma a leitura exatamente onde parou.

## Stack e Dependências
- Python 3.14+
- PyMuPDF (fitz) — extração de PDF com bounding boxes
- ebooklib — leitura de EPUB
- edge-tts — TTS online (pt-BR-FranciscaNeural)
- pyttsx3 — TTS offline fallback (Windows SAPI)
- sounddevice + soundfile — reprodução de áudio com pause/stop
- ffmpeg — conversão MP3 → WAV (requer instalação externa)
- tkinter — interface gráfica (stdlib)

## Estrutura de Arquivos
```
pdfvoz/
├── pdfvoz.py      # Entry point: argparse → CLI ou GUI
├── core.py        # Extração PDF/EPUB, detecção de capítulos, bookmark
├── tts_engine.py  # Motor TTS (edge-tts + pyttsx3), AudioPlayer
├── reader.py      # Loop de leitura com threading, controles navegação
├── cli_app.py     # Interface terminal com teclas interativas (msvcrt)
├── gui_app.py     # Interface Tkinter tema escuro
├── requirements.txt
├── .gitignore
├── README.md
├── LICENSE        # MIT
└── PROJECT.md
```

## Bookmark
Salvo em `~/.pdfvoz_bookmarks.json`:
```json
{
  "md5_hash_64kb": {
    "path": "caminho/livro.pdf",
    "chapter": 2,
    "paragraph": 47,
    "timestamp": "2026-04-14T10:30:00"
  }
}
```
O hash é calculado sobre os primeiros 64 KB do arquivo (identificação independente do nome).

## Comandos Essenciais
```bash
# Executar diretamente
python pdfvoz.py livro.pdf
python pdfvoz.py --gui

# Instalar dependências
pip install -r requirements.txt

# Build (futuro)
pyinstaller --onefile --console pdfvoz.py -n pdfvoz-cli
pyinstaller --onefile --noconsole pdfvoz.py -n pdfvoz
```

## Decisões Arquiteturais
- **AudioPlayer** reproduz numpy array com sounddevice em thread separada — permite pause/resume/stop sem bloquear UI
- **Reader._skip** (threading.Event): interrompe o speak_sync atual para navegação entre capítulos sem parar o loop principal
- **Geração assíncrona em thread**: asyncio.run() dentro de thread daemon para não bloquear o loop principal durante geração edge-tts
- **Bookmark salvo antes do speak_sync**: garante que posição não se perde se o app fechar durante a fala

## Estado Atual
- v1.1 — 2026-04-14
- Funcional: extração PDF/EPUB, TTS edge-tts + pyttsx3, CLI + GUI, bookmark
- Pré-buffer implementado: sem pausa entre parágrafos
- Ícone personalizado (livro + ondas sonoras)
- Executáveis instalados em C:\Windows\System32\

## Próximos Passos
- [ ] Suporte a velocidade sem alterar pitch (resample de áudio)
- [ ] Testar com livros reais e ajustar heurística de capítulos

## Problemas Conhecidos
- Gap de 1-3 segundos entre parágrafos (tempo de geração edge-tts)
- pyttsx3 pode não ter voz feminina instalada em todos os sistemas Windows
