#!/usr/bin/env python3
"""Coleta diária do Painel Diário Cometa.

Instagram: API oficial da Meta (Business Discovery) -> posts de cada perfil com data/hora.
Google:    Google Places API (New) -> nota média e total de avaliações de cada perfil.

Variáveis de ambiente (Secrets do repositório no GitHub):
  META_TOKEN         token de acesso da Meta (de preferência usuário do sistema, sem expiração)
  IG_USER_ID         ID da conta de Instagram comercial ligada ao token (a "conta que consulta")
  GOOGLE_PLACES_KEY  chave da Google Places API (New)

Sem dependências externas: só biblioteca padrão do Python 3.10+.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data"
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
FUSO = ZoneInfo(CONFIG.get("fuso", "America/Cuiaba"))
DIAS_GUARDADOS = 400  # quanto histórico de posts manter

META_TOKEN = os.environ.get("META_TOKEN", "").strip()
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
GOOGLE_KEY = os.environ.get("GOOGLE_PLACES_KEY", "").strip()
GRAPH = f"https://graph.facebook.com/{CONFIG.get('graph_api_versao', 'v22.0')}"


def ler_json(nome, padrao):
    p = DADOS / nome
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[aviso] {nome} corrompido, recomeçando", file=sys.stderr)
    return padrao


def gravar_json(nome, dados):
    DADOS.mkdir(exist_ok=True)
    (DADOS / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def http_json(url, metodo="GET", corpo=None, cabecalhos=None, tentativas=3):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cab = {"User-Agent": "painel-cometa/1.0", **(cabecalhos or {})}
    if dados:
        cab["Content-Type"] = "application/json"
    ultimo = None
    for _ in range(tentativas):
        try:
            req = urllib.request.Request(url, data=dados, headers=cab, method=metodo)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            texto = e.read().decode(errors="replace")[:500]
            ultimo = f"HTTP {e.code}: {texto}"
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:  # rede instável
            ultimo = str(e)
    raise RuntimeError(ultimo)


# ---------------------------------------------------------------- Instagram

def coletar_instagram(agora):
    base = ler_json("instagram.json", {})
    if not (META_TOKEN and IG_USER_ID):
        print("[aviso] META_TOKEN/IG_USER_ID ausentes: Instagram não coletado", file=sys.stderr)
        return base, False

    limite = (agora - timedelta(days=DIAS_GUARDADOS)).isoformat()
    ok = False
    for u in CONFIG["unidades"]:
        user = u["instagram"]
        reg = base.get(user, {"posts": []})
        campos = (
            f"business_discovery.username({user})"
            "{username,name,profile_picture_url,followers_count,media_count,"
            "media.limit(60){id,timestamp,media_type,media_product_type,permalink}}"
        )
        url = f"{GRAPH}/{IG_USER_ID}?" + urllib.parse.urlencode(
            {"fields": campos, "access_token": META_TOKEN})
        try:
            bd = http_json(url)["business_discovery"]
        except Exception as e:
            reg["erro"] = str(e)[:300]
            print(f"[erro] @{user}: {reg['erro']}", file=sys.stderr)
            base[user] = reg
            continue

        existentes = {p["id"]: p for p in reg.get("posts", [])}
        for m in bd.get("media", {}).get("data", []):
            existentes[m["id"]] = {
                "id": m["id"],
                "ts": m["timestamp"],
                "tipo": m.get("media_product_type") or m.get("media_type"),
                "link": m.get("permalink", ""),
            }
        # timestamps da Meta vêm como 2026-11-09T21:14:05+0000
        def norm(ts):
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").isoformat()
        posts = sorted(existentes.values(), key=lambda p: p["ts"], reverse=True)
        posts = [p for p in posts if norm(p["ts"]) >= limite]

        seg = reg.get("seguidores_hist", [])
        hoje = agora.astimezone(FUSO).date().isoformat()
        seg = [s for s in seg if s["data"] != hoje] + [
            {"data": hoje, "seguidores": bd.get("followers_count")}]

        base[user] = {
            "nome": bd.get("name") or u["nome"],
            "foto": bd.get("profile_picture_url", ""),
            "seguidores": bd.get("followers_count"),
            "total_posts": bd.get("media_count"),
            "seguidores_hist": seg[-120:],
            "posts": posts,
            "coletado_em": agora.isoformat(),
        }
        ok = True
        print(f"[ok] @{user}: {len(posts)} posts no histórico")
    if not ok:
        diagnosticar_meta()
    return base, ok


def diagnosticar_meta():
    """Mostra no log o que o token enxerga (sem expor o token)."""
    print("---- diagnóstico Meta ----")
    testes = {
        "quem é o token": f"{GRAPH}/me?fields=id,name",
        "permissões concedidas": f"{GRAPH}/me/permissions",
        "Páginas visíveis": f"{GRAPH}/me/accounts?fields=name,instagram_business_account&limit=50",
        "conta IG_USER_ID": f"{GRAPH}/{IG_USER_ID}?fields=id,username",
    }
    for nome, url in testes.items():
        sep = "&" if "?" in url else "?"
        try:
            r = http_json(url + sep + "access_token=" + urllib.parse.quote(META_TOKEN), tentativas=1)
            if nome == "permissões concedidas":
                r = [f"{p['permission']}={p['status']}" for p in r.get("data", [])]
            print(f"[diag] {nome}: {json.dumps(r, ensure_ascii=False)[:600]}")
        except Exception as e:
            print(f"[diag] {nome}: ERRO {str(e)[:300]}")
    print("---- fim do diagnóstico ----")


# ---------------------------------------------------------------- Google

PLACES = "https://places.googleapis.com/v1"
CAMPOS_DET = "id,displayName,formattedAddress,rating,userRatingCount,googleMapsUri"


def nome_do_link(link):
    """Segue o link share.google e tenta extrair o nome do negócio do destino."""
    url = link
    for _ in range(6):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="GET")

        class SemRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        abridor = urllib.request.build_opener(SemRedirect)
        try:
            r = abridor.open(req, timeout=20)
            break
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = urllib.parse.urljoin(url, e.headers["Location"])
                continue
            break
        except Exception:
            break
    p = urllib.parse.urlparse(url)
    if "/maps/place/" in p.path:
        return urllib.parse.unquote_plus(p.path.split("/maps/place/")[1].split("/")[0])
    q = urllib.parse.parse_qs(p.query).get("q")
    return q[0] if q else None


def resolver_place_id(u, cache):
    if u.get("google_place_id"):
        return u["google_place_id"]
    if u["id"] in cache:
        return cache[u["id"]]["place_id"]
    consulta = None
    if u.get("google_link"):
        try:
            consulta = nome_do_link(u["google_link"])
        except Exception:
            consulta = None
    consulta = consulta or u["google_busca"]
    r = http_json(
        f"{PLACES}/places:searchText", "POST",
        {"textQuery": consulta, "languageCode": "pt-BR", "regionCode": "BR"},
        {"X-Goog-Api-Key": GOOGLE_KEY,
         "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress"},
    )
    lugares = r.get("places", [])
    if not lugares:
        raise RuntimeError(f"nenhum resultado para '{consulta}'")
    pid = lugares[0]["id"]
    cache[u["id"]] = {"place_id": pid, "consulta": consulta,
                      "nome": lugares[0].get("displayName", {}).get("text", "")}
    return pid


APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
APIFY_ATOR = "compass~crawler-google-places"


def coletar_google_apify(agora, base, cache):
    """Nota e total de avaliações via Apify (Google Maps Scraper), numa única execução."""
    hoje = agora.astimezone(FUSO).date().isoformat()
    ok = False
    for u in CONFIG["unidades"]:
        reg = base.get(u["id"], {"historico": []})
        pid = u.get("google_place_id") or cache.get(u["id"], {}).get("place_id")
        entrada = {"language": "pt-BR", "maxReviews": 0, "maxImages": 0,
                   "scrapeContacts": False, "skipClosedPlaces": False}
        if pid:
            entrada["startUrls"] = [{"url": f"https://www.google.com/maps/search/?api=1&query=Google&query_place_id={pid}"}]
        else:
            entrada["searchStringsArray"] = [u["google_busca"]]
            entrada["maxCrawledPlacesPerSearch"] = 1
        url = (f"https://api.apify.com/v2/acts/{APIFY_ATOR}/run-sync-get-dataset-items?"
               + urllib.parse.urlencode({"token": APIFY_TOKEN, "timeout": 240}))
        try:
            itens = http_json(url, "POST", entrada, tentativas=2)
            if not itens:
                raise RuntimeError("nenhum resultado no Google Maps")
            d = itens[0]
        except Exception as e:
            reg["erro"] = str(e).replace(APIFY_TOKEN, "***")[:300]
            print(f"[erro] Google {u['id']}: {reg['erro']}", file=sys.stderr)
            base[u["id"]] = reg
            continue
        novo_pid = d.get("placeId") or pid or ""
        if novo_pid and u["id"] not in cache:
            cache[u["id"]] = {"place_id": novo_pid, "consulta": u["google_busca"], "nome": d.get("title", "")}
        hist = [h for h in reg.get("historico", []) if h["data"] != hoje]
        hist.append({"data": hoje, "nota": d.get("totalScore"), "total": d.get("reviewsCount") or 0})
        base[u["id"]] = {
            "place_id": novo_pid,
            "nome_google": d.get("title", ""),
            "endereco": d.get("address", ""),
            "link_maps": d.get("url", ""),
            "historico": hist[-DIAS_GUARDADOS:],
        }
        ok = True
        print(f"[ok] Google {u['id']}: {d.get('title')} · nota {d.get('totalScore')} · {d.get('reviewsCount')} avaliações")
    return base, cache, ok


def coletar_google(agora):
    base = ler_json("google.json", {})
    cache = ler_json("places.json", {})
    if not GOOGLE_KEY and APIFY_TOKEN:
        return coletar_google_apify(agora, base, cache)
    if not GOOGLE_KEY:
        print("[aviso] Sem GOOGLE_PLACES_KEY nem APIFY_TOKEN: Google não coletado", file=sys.stderr)
        return base, cache, False
    hoje = agora.astimezone(FUSO).date().isoformat()
    ok = False
    for u in CONFIG["unidades"]:
        reg = base.get(u["id"], {"historico": []})
        try:
            pid = resolver_place_id(u, cache)
            d = http_json(f"{PLACES}/places/{pid}?languageCode=pt-BR",
                          cabecalhos={"X-Goog-Api-Key": GOOGLE_KEY, "X-Goog-FieldMask": CAMPOS_DET})
        except Exception as e:
            reg["erro"] = str(e)[:300]
            print(f"[erro] Google {u['id']}: {reg['erro']}", file=sys.stderr)
            base[u["id"]] = reg
            continue
        hist = [h for h in reg.get("historico", []) if h["data"] != hoje]
        hist.append({"data": hoje, "nota": d.get("rating"), "total": d.get("userRatingCount", 0)})
        base[u["id"]] = {
            "place_id": pid,
            "nome_google": d.get("displayName", {}).get("text", ""),
            "endereco": d.get("formattedAddress", ""),
            "link_maps": d.get("googleMapsUri", ""),
            "historico": hist[-DIAS_GUARDADOS:],
        }
        ok = True
        print(f"[ok] Google {u['id']}: nota {d.get('rating')} · {d.get('userRatingCount')} avaliações")
    return base, cache, ok


def main():
    agora = datetime.now(timezone.utc)
    ig, ok_ig = coletar_instagram(agora)
    gg, cache, ok_gg = coletar_google(agora)
    gravar_json("instagram.json", ig)
    gravar_json("google.json", gg)
    gravar_json("places.json", cache)
    meta = ler_json("meta.json", {})
    meta.update({
        "atualizado_em": agora.isoformat(),
        "fuso": CONFIG.get("fuso"),
        "amostra": False,
        "instagram_ok": ok_ig,
        "google_ok": ok_gg,
        "unidades": [{k: u[k] for k in ("id", "nome", "cidade", "marca", "instagram")}
                     for u in CONFIG["unidades"]],
    })
    gravar_json("meta.json", meta)
    if not (ok_ig or ok_gg):
        sys.exit("Nada foi coletado. Confira os Secrets do repositório.")


if __name__ == "__main__":
    main()
