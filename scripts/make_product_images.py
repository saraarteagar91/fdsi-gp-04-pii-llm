"""
Genera las ilustraciones de producto (SVG) del catálogo en
static/img/products/<sku>.svg, con un estilo uniforme de estudio:
fondo suave, sombra al piso y el producto dibujado con formas planas.

Uso:
    python -m scripts.make_product_images
"""
from pathlib import Path

OUT = Path("static/img/products")

DARK, DARK2, SILVER, WHITE = "#23272f", "#3a404b", "#c7ccd4", "#f5f6f8"


def frame(body: str, bg1: str, bg2: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" role="img">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient>
  <linearGradient id="metal" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#eef0f3"/><stop offset="1" stop-color="#b9bfc8"/></linearGradient>
  <linearGradient id="screen" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2b5cff"/><stop offset=".55" stop-color="#7a3cff"/><stop offset="1" stop-color="#ff5c8a"/></linearGradient>
  <linearGradient id="glass" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#dff1ff" stop-opacity=".9"/><stop offset="1" stop-color="#a9d3f5" stop-opacity=".7"/></linearGradient>
  <linearGradient id="gloss" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <radialGradient id="shadow"><stop offset="0" stop-color="#000" stop-opacity=".22"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
</defs>
<rect width="800" height="800" fill="url(#bg)"/>
<ellipse cx="400" cy="660" rx="250" ry="34" fill="url(#shadow)"/>
{body}
</svg>
"""


PRODUCTS = {
    # Audífonos
    "SM-AUD-01": (frame(f"""
<path d="M230 430 C230 230 570 230 570 430" fill="none" stroke="{DARK}" stroke-width="34" stroke-linecap="round"/>
<path d="M245 420 C250 260 550 260 555 420" fill="none" stroke="{DARK2}" stroke-width="10" stroke-linecap="round"/>
<rect x="180" y="400" width="120" height="200" rx="56" fill="{DARK}"/>
<rect x="500" y="400" width="120" height="200" rx="56" fill="{DARK}"/>
<rect x="268" y="420" width="44" height="160" rx="22" fill="#4a5160"/>
<rect x="488" y="420" width="44" height="160" rx="22" fill="#4a5160"/>
<rect x="196" y="420" width="40" height="70" rx="20" fill="url(#gloss)"/>
<rect x="516" y="420" width="40" height="70" rx="20" fill="url(#gloss)"/>
<circle cx="560" cy="560" r="7" fill="#1fd1a5"/>""", "#eef2ff", "#d9e1ff")),
    # Licuadora
    "PM-LIC-600": (frame(f"""
<path d="M300 200 L500 200 L470 480 L330 480 Z" fill="url(#glass)" stroke="#8fb9dc" stroke-width="6"/>
<path d="M500 250 C560 250 570 300 560 360 C552 410 520 420 488 410" fill="none" stroke="#8fb9dc" stroke-width="14"/>
<rect x="285" y="178" width="230" height="36" rx="12" fill="{DARK}"/>
<rect x="380" y="150" width="40" height="34" rx="8" fill="{DARK2}"/>
<path d="M345 330 C380 300 420 360 455 330 L465 470 L335 470 Z" fill="#ff8a5c" opacity=".75"/>
<path d="M370 460 L430 440 M370 440 L430 460" stroke="{SILVER}" stroke-width="8" stroke-linecap="round"/>
<path d="M300 480 L500 480 L530 640 L270 640 Z" fill="{DARK}"/>
<circle cx="400" cy="565" r="40" fill="#4a5160"/><circle cx="400" cy="565" r="26" fill="url(#metal)"/>
<rect x="392" y="540" width="16" height="22" rx="6" fill="{DARK}"/>
<rect x="320" y="210" width="26" height="250" rx="13" fill="url(#gloss)"/>""", "#fff3ea", "#ffe0cc")),
    # Portátil
    "AB-14": (frame(f"""
<rect x="190" y="200" width="420" height="290" rx="18" fill="{DARK}"/>
<rect x="210" y="220" width="380" height="250" rx="6" fill="url(#screen)"/>
<path d="M210 420 L330 330 L410 390 L480 340 L590 420 L590 470 L210 470 Z" fill="#fff" opacity=".18"/>
<circle cx="520" cy="280" r="26" fill="#fff" opacity=".35"/>
<path d="M150 500 L650 500 L690 600 L110 600 Z" fill="url(#metal)"/>
<rect x="110" y="596" width="580" height="16" rx="8" fill="#9aa1ab"/>
<g fill="#a7aeb8">{''.join(f'<rect x="{200 + c * 34}" y="{512 + r * 22}" width="28" height="16" rx="3"/>' for r in range(3) for c in range(12))}</g>
<rect x="350" y="580" width="100" height="14" rx="4" fill="#aeb4bd"/>""", "#eaf6ff", "#d3e9fb")),
    # Smartwatch
    "FIT-2": (frame(f"""
<rect x="330" y="120" width="140" height="190" rx="30" fill="#2f6f6a"/>
<rect x="330" y="490" width="140" height="190" rx="30" fill="#2f6f6a"/>
<g fill="#255a56">{''.join(f'<circle cx="400" cy="{560 + i * 30}" r="7"/>' for i in range(3))}</g>
<rect x="280" y="250" width="240" height="300" rx="64" fill="{DARK}"/>
<rect x="298" y="268" width="204" height="264" rx="50" fill="#0e1117"/>
<circle cx="400" cy="400" r="86" fill="none" stroke="#1fd1a5" stroke-width="12" stroke-dasharray="380 200" stroke-linecap="round" transform="rotate(-90 400 400)"/>
<circle cx="400" cy="400" r="64" fill="none" stroke="#ff5c8a" stroke-width="10" stroke-dasharray="250 200" stroke-linecap="round" transform="rotate(-90 400 400)"/>
<text x="400" y="412" text-anchor="middle" font-family="Segoe UI, Arial" font-size="40" font-weight="700" fill="#fff">10:09</text>
<rect x="520" y="350" width="16" height="60" rx="8" fill="{DARK2}"/>
<rect x="300" y="270" width="80" height="80" rx="40" fill="url(#gloss)"/>""", "#e9fbf5", "#cdf1e5")),
    # Cafetera
    "CAF-DUO": (frame(f"""
<rect x="230" y="170" width="340" height="120" rx="24" fill="{DARK}"/>
<rect x="250" y="280" width="300" height="300" rx="16" fill="url(#metal)"/>
<rect x="230" y="560" width="340" height="60" rx="16" fill="{DARK}"/>
<rect x="290" y="300" width="220" height="40" rx="10" fill="{DARK2}"/>
<circle cx="320" cy="220" r="22" fill="#4a5160"/><circle cx="480" cy="220" r="22" fill="#4a5160"/>
<circle cx="400" cy="220" r="14" fill="#1fd1a5"/>
<path d="M300 340 L500 340 L470 380 L330 380 Z" fill="{DARK}"/>
<path d="M500 360 L620 360" stroke="{DARK}" stroke-width="18" stroke-linecap="round"/>
<path d="M350 430 h50 v70 a25 25 0 0 1 -25 25 a25 25 0 0 1 -25 -25 Z" fill="#fff"/>
<path d="M410 430 h50 v70 a25 25 0 0 1 -25 25 a25 25 0 0 1 -25 -25 Z" fill="#fff"/>
<rect x="352" y="434" width="46" height="18" fill="#6b3e26"/><rect x="412" y="434" width="46" height="18" fill="#6b3e26"/>
<path d="M375 410 c-10 -15 10 -20 0 -35 M435 410 c-10 -15 10 -20 0 -35" stroke="#9aa1ab" stroke-width="5" fill="none" stroke-linecap="round"/>
<path d="M550 380 L570 520" stroke="{SILVER}" stroke-width="10" stroke-linecap="round"/>""", "#fbf3ec", "#efdfd0")),
    # Televisor
    "TV-55": (frame(f"""
<rect x="110" y="170" width="580" height="350" rx="14" fill="{DARK}"/>
<rect x="124" y="184" width="552" height="322" rx="6" fill="url(#screen)"/>
<path d="M124 430 L260 320 L360 400 L470 300 L676 460 L676 506 L124 506 Z" fill="#0f1a3d" opacity=".55"/>
<path d="M124 470 L300 390 L420 450 L560 380 L676 440 L676 506 L124 506 Z" fill="#0b1230" opacity=".7"/>
<circle cx="560" cy="260" r="34" fill="#ffd36e" opacity=".9"/>
<rect x="124" y="184" width="552" height="120" fill="url(#gloss)"/>
<path d="M360 520 L330 620 M440 520 L470 620" stroke="{DARK2}" stroke-width="16" stroke-linecap="round"/>
<rect x="280" y="612" width="240" height="16" rx="8" fill="{DARK}"/>""", "#eef1f7", "#d8dee9")),
    # Celular
    "PH-A5": (frame(f"""
<rect x="430" y="150" width="200" height="420" rx="36" fill="#5b4fd6" transform="rotate(8 530 360)"/>
<rect x="455" y="180" width="80" height="120" rx="24" fill="#3c32a8" transform="rotate(8 530 360)"/>
<circle cx="500" cy="225" r="20" fill="#11131a" transform="rotate(8 530 360)"/><circle cx="500" cy="270" r="20" fill="#11131a" transform="rotate(8 530 360)"/>
<rect x="210" y="160" width="220" height="460" rx="40" fill="{DARK}"/>
<rect x="224" y="174" width="192" height="432" rx="30" fill="url(#screen)"/>
<circle cx="320" cy="200" r="9" fill="#0e1117"/>
<g fill="#fff" opacity=".85">{''.join(f'<rect x="{248 + c * 44}" y="{300 + r * 54}" width="32" height="32" rx="9"/>' for r in range(4) for c in range(4))}</g>
<text x="320" y="270" text-anchor="middle" font-family="Segoe UI, Arial" font-size="40" font-weight="300" fill="#fff">9:41</text>
<rect x="226" y="176" width="90" height="200" rx="28" fill="url(#gloss)"/>""", "#f1efff", "#ddd8ff")),
    # Parlante
    "SPK-BOOM": (frame(f"""
<rect x="290" y="170" width="220" height="440" rx="100" fill="#e2493b"/>
<rect x="290" y="170" width="220" height="440" rx="100" fill="url(#gloss)"/>
<g fill="#b8352a">{''.join(f'<circle cx="{318 + c * 24 + (r % 2) * 12}" cy="{250 + r * 22}" r="5"/>' for r in range(14) for c in range(7))}</g>
<rect x="290" y="170" width="220" height="70" rx="40" fill="{DARK}"/>
<circle cx="350" cy="205" r="12" fill="#4a5160"/><circle cx="400" cy="205" r="12" fill="#4a5160"/><circle cx="450" cy="205" r="12" fill="#4a5160"/>
<rect x="290" y="560" width="220" height="50" rx="25" fill="{DARK}"/>
<path d="M560 330 c30 30 30 90 0 120 M590 300 c50 50 50 130 0 180" stroke="#e2493b" stroke-width="10" fill="none" stroke-linecap="round" opacity=".5"/>""", "#fff0ee", "#ffd9d4")),
    # Freidora de aire
    "AIR-5L": (frame(f"""
<rect x="240" y="170" width="320" height="460" rx="70" fill="{DARK}"/>
<rect x="240" y="170" width="320" height="200" rx="70" fill="url(#gloss)"/>
<rect x="300" y="210" width="200" height="90" rx="20" fill="#0e1117"/>
<text x="400" y="268" text-anchor="middle" font-family="Segoe UI, Arial" font-size="38" font-weight="700" fill="#ff8a3c">180°</text>
<circle cx="330" cy="330" r="10" fill="#4a5160"/><circle cx="400" cy="330" r="10" fill="#1fd1a5"/><circle cx="470" cy="330" r="10" fill="#4a5160"/>
<rect x="265" y="370" width="270" height="230" rx="40" fill="#2c313a"/>
<rect x="340" y="450" width="120" height="44" rx="20" fill="{SILVER}"/>
<g fill="#3d434e">{''.join(f'<rect x="{290 + i * 36}" y="540" width="20" height="40" rx="6"/>' for i in range(7))}</g>""", "#fff6ea", "#ffe6c7")),
    # Aspiradora robot
    "VAC-R3": (frame(f"""
<ellipse cx="400" cy="470" rx="250" ry="110" fill="#1b1e24"/>
<ellipse cx="400" cy="440" rx="250" ry="110" fill="{DARK}"/>
<ellipse cx="400" cy="430" rx="215" ry="88" fill="#2f3540"/>
<ellipse cx="400" cy="400" rx="60" ry="30" fill="#4a5160"/>
<ellipse cx="400" cy="392" rx="46" ry="22" fill="#5c6474"/>
<ellipse cx="400" cy="480" rx="26" ry="10" fill="#1fd1a5"/>
<path d="M170 440 C200 360 600 360 630 440" fill="none" stroke="#fff" stroke-opacity=".15" stroke-width="10"/>
<path d="M600 520 l70 40 M610 500 l80 20" stroke="#9aa1ab" stroke-width="5" stroke-linecap="round"/>""", "#eef6f4", "#d5ebe5")),
    # Teclado
    "KB-MX": (frame(f"""
<path d="M120 380 L680 380 L720 560 L80 560 Z" fill="{DARK}"/>
<path d="M80 560 L720 560 L720 590 L80 590 Z" fill="#14171c"/>
<g fill="#f2f3f5">{''.join(f'<path d="M{150 + c * 42 - r * 10 + r * 0} {398 + r * 38} h34 l2 28 h-38 Z"/>' for r in range(4) for c in range(13))}</g>
<path d="M260 552 h280 l-2 -26 h-276 Z" fill="#f2f3f5"/>
<rect x="640" y="392" width="20" height="8" rx="4" fill="#1fd1a5"/>""", "#f2f2f4", "#dcdde3")),
    # Impresora
    "PRN-INK": (frame(f"""
<rect x="250" y="160" width="300" height="140" fill="#fff" stroke="#d7dbe1" stroke-width="4"/>
<path d="M280 190 h200 M280 220 h240 M280 250 h160" stroke="#c7ccd4" stroke-width="10" stroke-linecap="round"/>
<rect x="170" y="290" width="460" height="230" rx="28" fill="url(#metal)"/>
<rect x="170" y="290" width="460" height="60" rx="28" fill="{DARK}"/>
<rect x="470" y="370" width="130" height="70" rx="10" fill="#0e1117"/>
<rect x="484" y="384" width="62" height="42" rx="4" fill="#2b5cff"/>
<circle cx="572" cy="405" r="10" fill="#1fd1a5"/>
<rect x="210" y="470" width="380" height="24" rx="6" fill="#9aa1ab"/>
<path d="M230 494 L570 494 L600 600 L200 600 Z" fill="#fff" stroke="#d7dbe1" stroke-width="4"/>
<path d="M270 530 h180 M265 560 h240" stroke="#c7ccd4" stroke-width="8" stroke-linecap="round"/>""", "#f1f4f8", "#dde3ec")),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for sku, svg in PRODUCTS.items():
        (OUT / f"{sku}.svg").write_text(svg, encoding="utf-8")
    print(f"{len(PRODUCTS)} imágenes en {OUT}")


if __name__ == "__main__":
    main()
