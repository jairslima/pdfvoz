"""Gera o ícone pdfvoz.ico para uso no PyInstaller."""
from PIL import Image, ImageDraw
import math

BG      = (30, 30, 46)       # #1e1e2e
BLUE    = (137, 180, 250)    # #89b4fa
WHITE   = (205, 214, 244)    # #cdd6f4
YELLOW  = (249, 226, 175)    # #f9e2af


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size

    # Fundo arredondado
    r = s // 8
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=BG)

    # --- Livro (lado esquerdo) ---
    bx0 = int(s * 0.08)
    bx1 = int(s * 0.52)
    by0 = int(s * 0.18)
    by1 = int(s * 0.82)
    br  = max(2, s // 32)

    # Capa do livro
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=br, fill=BLUE)

    # Lombada
    spine_w = max(2, s // 20)
    d.rounded_rectangle([bx0, by0, bx0 + spine_w, by1], radius=br, fill=WHITE)

    # Linhas de texto simuladas
    line_color = (30, 30, 46, 180)
    lx0 = bx0 + spine_w + max(2, s // 24)
    lx1 = bx1 - max(2, s // 24)
    n_lines = 6
    gap = (by1 - by0) // (n_lines + 2)
    for i in range(1, n_lines + 1):
        ly = by0 + gap * (i + 0) + gap // 2
        # linhas mais curtas no final
        lx1_adj = lx1 if i < n_lines else lx0 + (lx1 - lx0) * 2 // 3
        lh = max(1, s // 40)
        d.rectangle([lx0, ly, lx1_adj, ly + lh], fill=line_color)

    # --- Ondas sonoras (lado direito) ---
    # Centro vertical do livro
    cy = (by0 + by1) // 2
    ox = int(s * 0.60)   # ponto de origem das ondas

    wave_color_dim = (*YELLOW[:3], 180)
    wave_color     = (*YELLOW[:3], 230)

    # 3 arcos concêntricos
    arcs = [
        (int(s * 0.10), int(s * 0.16), wave_color_dim),
        (int(s * 0.16), int(s * 0.26), wave_color),
        (int(s * 0.22), int(s * 0.35), YELLOW),
    ]
    for radius, thick_half, color in arcs:
        for lw in range(max(1, s // 60)):
            r_outer = radius + lw
            # Arco: de -60° a +60° (abertura para a direita)
            d.arc(
                [ox - r_outer, cy - r_outer, ox + r_outer, cy + r_outer],
                start=-60, end=60,
                fill=color, width=max(1, s // 40),
            )

    # Ponto central (alto-falante)
    dot_r = max(2, s // 18)
    d.ellipse([ox - dot_r, cy - dot_r, ox + dot_r, cy + dot_r], fill=YELLOW)

    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw_icon(sz) for sz in sizes]

    # Salva .ico com todas as resoluções
    ico_path = "pdfvoz.ico"
    frames[0].save(
        ico_path,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[1:],
    )
    print(f"Ícone gerado: {ico_path}")

    # Também salva PNG 256 para referência
    frames[-1].save("pdfvoz_preview.png")
    print("Preview salvo: pdfvoz_preview.png")


if __name__ == "__main__":
    main()
