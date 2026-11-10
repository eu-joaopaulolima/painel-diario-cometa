#!/usr/bin/env python3
"""Monta o index.html publicado no GitHub Pages a partir de src/painel.html."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
corpo = (RAIZ / "src" / "painel.html").read_text(encoding="utf-8")
cabeca, _, resto = corpo.partition("<div class=\"wrap\">")
html = (
    "<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
    "<meta name=\"robots\" content=\"noindex\">\n"
    "<style>body{margin:0}[hidden]{display:none!important}"
    ":root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}</style>\n"
    + cabeca + "</head>\n<body>\n<div class=\"wrap\">" + resto + "\n</body>\n</html>\n"
)
(RAIZ / "index.html").write_text(html, encoding="utf-8")
print("index.html montado")
