#!/usr/bin/env python3
"""Gera dados de EXEMPLO (marcados como amostra) só para visualizar o painel antes da 1ª coleta real."""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data"
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
FUSO = ZoneInfo(CONFIG["fuso"])
random.seed(7)

agora = datetime.now(timezone.utc).replace(hour=11, minute=3, second=0, microsecond=0)
hoje_local = agora.astimezone(FUSO).date()
ritmo = [1.4, 0.9, 1.1, 0.5, 0.25, 1.0, 1.8, 0.7]  # posts médios por dia por perfil
seg_base = [8400, 11200, 9800, 14300, 4100, 7600, 23500, 6200]
notas = [4.7, 4.8, 4.6, 4.9, 4.5, 4.6, 4.4, 4.7]
totais = [312, 540, 488, 702, 96, 410, 1210, 188]

ig, gg = {}, {}
for i, u in enumerate(CONFIG["unidades"]):
    posts = []
    for d in range(1, 61):
        dia = hoje_local - timedelta(days=d)
        n = sum(1 for _ in range(4) if random.random() < ritmo[i] / 4)
        for _ in range(n):
            h = random.randint(8, 20)
            ts = datetime(dia.year, dia.month, dia.day, h, random.randint(0, 59), tzinfo=FUSO)
            posts.append({"id": f"{i}{d}{h}{random.randint(0,999)}",
                          "ts": ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000"),
                          "tipo": random.choice(["FEED", "REELS", "REELS", "FEED"]),
                          "link": f"https://www.instagram.com/{u['instagram']}/"})
    posts.sort(key=lambda p: p["ts"], reverse=True)
    ig[u["instagram"]] = {
        "nome": u["nome"], "foto": "", "seguidores": seg_base[i], "total_posts": 900 + i * 130,
        "seguidores_hist": [{"data": (hoje_local - timedelta(days=d)).isoformat(),
                             "seguidores": seg_base[i] - d * random.randint(2, 9)} for d in range(30, -1, -1)],
        "posts": posts, "coletado_em": agora.isoformat(),
    }
    hist, tot, nota = [], totais[i], notas[i]
    for d in range(45, -1, -1):
        tot += random.choice([0, 0, 0, 1, 1, 2]) if d < 45 else 0
        hist.append({"data": (hoje_local - timedelta(days=d)).isoformat(),
                     "nota": round(nota + random.uniform(-0.05, 0.02), 1), "total": tot})
    gg[u["id"]] = {"place_id": "exemplo", "nome_google": u["nome"], "endereco": u["cidade"],
                   "link_maps": "", "historico": hist}

meta = {"atualizado_em": agora.isoformat(), "fuso": CONFIG["fuso"], "amostra": True,
        "instagram_ok": True, "google_ok": True,
        "unidades": [{k: u[k] for k in ("id", "nome", "cidade", "marca", "instagram")}
                     for u in CONFIG["unidades"]]}
DADOS.mkdir(exist_ok=True)
for nome, obj in (("instagram.json", ig), ("google.json", gg), ("meta.json", meta)):
    (DADOS / nome).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
print("amostra gerada em", DADOS)
