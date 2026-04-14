# PDF Voz by Jair Lima

Leitor de PDF e EPUB com Text-to-Speech. Voz feminina (pt-BR-FranciscaNeural via Microsoft Edge TTS), marcador de posição automático, suporte a terminal e interface gráfica.

## Instalação

```bash
pip install -r requirements.txt
```

Requer **ffmpeg** instalado e no PATH.

## Uso — Terminal

```bash
# Iniciar ou retomar leitura
pdfvoz livro.pdf

# Listar capítulos
pdfvoz livro.pdf --listar

# Iniciar do capítulo 3
pdfvoz livro.pdf --capitulo 3

# Reiniciar do início (ignora bookmark)
pdfvoz livro.pdf --reiniciar

# Velocidade 1.5x
pdfvoz livro.pdf --velocidade 1.5

# Modo offline (pyttsx3, sem internet)
pdfvoz livro.pdf --offline

# Abrir interface gráfica
pdfvoz livro.pdf --gui
pdfvoz
```

### Teclas durante a leitura

| Tecla | Ação |
|-------|------|
| `P` ou `Espaço` | Pausar / Retomar |
| `N` | Próximo capítulo |
| `B` | Capítulo anterior |
| `R` | Voltar ao início |
| `Q` | Parar e sair (salva posição) |

## Uso — Interface Gráfica

Execute `pdfvoz` ou `pdfvoz --gui`. Clique em **Abrir PDF/EPUB** e use os botões:

- **|◄** — Voltar ao início
- **◄** — Capítulo anterior
- **▶ / ⏸** — Play / Pause
- **►** — Próximo capítulo
- **■** — Parar (salva posição)

O dropdown de capítulos permite saltar diretamente para qualquer parte do livro.

## Funcionalidades

- Voz feminina natural em português (pt-BR-FranciscaNeural)
- Fallback automático para pyttsx3 quando sem internet
- Remove cabeçalhos e rodapés automaticamente
- Detecta índice/sumário e inicia leitura no Capítulo 1
- Salva posição exata (capítulo + parágrafo) em `~/.pdfvoz_bookmarks.json`
- Suporte a PDF (PyMuPDF) e EPUB (ebooklib)
- Controle de velocidade: 0.5x a 3.0x

## Dependências

- PyMuPDF (extração de PDF)
- ebooklib (leitura de EPUB)
- edge-tts (TTS online)
- pyttsx3 (TTS offline)
- sounddevice + soundfile (reprodução de áudio)
- ffmpeg (conversão MP3 → WAV)

## Licença

MIT License — Copyright (c) 2026 Jair Lima
