from __future__ import annotations

import io
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any

from flask import Flask, Response, jsonify, redirect, render_template_string, request, send_file
from PIL import Image


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_JSON = os.path.join(BASE_DIR, "clubs_data.json")
LOGOS_DIR = os.path.join(BASE_DIR, "LOGOS")
DOCS_LOGOS_DIR = os.path.join(BASE_DIR, "docs", "LOGOS")
EXTRACT_SCRIPT = os.path.join(BASE_DIR, "extract_clubs.py")


app = Flask(__name__)


@dataclass(frozen=True)
class Club:
    id: int
    nombre: str
    ciudad: str
    provincia: str
    ubicacion: str
    division: str
    has_logo: bool


CLUBS: list[Club] = []


def load_clubs() -> None:
    global CLUBS
    if not os.path.exists(DATA_JSON):
        CLUBS = []
        return

    with open(DATA_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)

    clubs: list[Club] = []
    for c in raw:
        try:
            clubs.append(
                Club(
                    id=int(c.get("id")),
                    nombre=str(c.get("nombre") or ""),
                    ciudad=str(c.get("ciudad") or ""),
                    provincia=str(c.get("provincia") or ""),
                    ubicacion=str(c.get("ubicacion") or ""),
                    division=str(c.get("division") or ""),
                    has_logo=bool(c.get("has_logo")),
                )
            )
        except Exception:
            continue

    CLUBS = clubs


def normalize(s: str) -> str:
    return " ".join((s or "").lower().strip().split())


def ensure_dirs() -> None:
    os.makedirs(LOGOS_DIR, exist_ok=True)
    os.makedirs(DOCS_LOGOS_DIR, exist_ok=True)


def logo_path(club_id: int) -> str:
    return os.path.join(LOGOS_DIR, f"{club_id}.png")


def docs_logo_path(club_id: int) -> str:
    return os.path.join(DOCS_LOGOS_DIR, f"{club_id}.png")


def club_has_logo_file(club_id: int) -> bool:
    return os.path.exists(logo_path(club_id)) or os.path.exists(docs_logo_path(club_id))


def process_image_to_png(file_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(file_bytes)) as img:
        img = img.convert("RGBA")
        img.thumbnail((128, 128), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()


def run_extract_exports() -> tuple[bool, str]:
    if not os.path.exists(EXTRACT_SCRIPT):
        return False, "No se encontró extract_clubs.py"

    try:
        proc = subprocess.run(
            ["python", EXTRACT_SCRIPT],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            return False, output.strip() or "Error al regenerar exports"
        return True, output.strip() or "OK"
    except Exception as e:
        return False, str(e)


HTML = """
<!doctype html>
<html lang=\"es\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Logo Manager</title>
  <style>
    *{box-sizing:border-box;font-family:Arial,sans-serif}
    body{margin:0;background:#f6f7fb;color:#222}
    header{position:sticky;top:0;background:#0b5ed7;color:#fff;padding:14px 16px;z-index:10}
    header h1{margin:0;font-size:16px}
    main{max-width:900px;margin:0 auto;padding:16px}
    .card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.06);padding:14px}
    .row{display:flex;gap:12px;flex-wrap:wrap}
    .col{flex:1;min-width:260px}
    label{display:block;font-size:12px;color:#555;margin-bottom:6px}
    input[type=text]{width:100%;padding:10px 12px;border:1px solid #d1d5db;border-radius:8px}
    button{padding:10px 12px;border:0;border-radius:8px;background:#0b5ed7;color:#fff;font-weight:700;cursor:pointer}
    button:disabled{opacity:.6;cursor:not-allowed}
    .muted{color:#6b7280;font-size:12px}
    .results{margin-top:10px;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden}
    .result{padding:10px 12px;border-top:1px solid #e5e7eb;display:flex;gap:10px;align-items:center;cursor:pointer}
    .result:first-child{border-top:0}
    .result:hover{background:#f3f4f6}
    .badge{font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid #e5e7eb;color:#374151}
    .badge.ok{background:#ecfdf5;border-color:#10b981;color:#065f46}
    .badge.no{background:#fef2f2;border-color:#ef4444;color:#7f1d1d}
    .preview{display:flex;gap:12px;align-items:center}
    .logo{width:64px;height:64px;border-radius:12px;border:1px solid #e5e7eb;background:#fff;object-fit:contain}
    .kv{font-size:13px;line-height:1.35}
    .kv b{display:inline-block;min-width:90px}
    .actions{margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
    input[type=file]{max-width:100%}
    .status{margin-top:10px;font-size:13px;white-space:pre-wrap}
    .stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
    .stat{background:#f3f4f6;border:1px solid #e5e7eb;border-radius:8px;padding:10px 14px;font-size:13px}
    .stat b{display:block;font-size:18px}
    .tabs{display:flex;gap:8px;margin-bottom:10px;border-bottom:1px solid #e5e7eb}
    .tab{padding:8px 12px;background:none;border:0;border-bottom:2px solid transparent;cursor:pointer;font-weight:700;color:#6b7280}
    .tab.active{color:#0b5ed7;border-bottom-color:#0b5ed7}
    .list{max-height:400px;overflow:auto;border:1px solid #e5e7eb;border-radius:8px}
    .list-item{padding:10px 12px;border-top:1px solid #e5e7eb;display:flex;gap:10px;align-items:center;cursor:pointer}
    .list-item:first-child{border-top:0}
    .list-item:hover{background:#f3f4f6}
    .list-item img{width:40px;height:40px;border-radius:8px;object-fit:contain;border:1px solid #e5e7eb;background:#fff}
    .list-item .info{flex:1}
    .list-item .name{font-weight:700;font-size:13px}
    .list-item .meta{font-size:12px;color:#6b7280}
    .empty{padding:20px;text-align:center;color:#6b7280;font-size:13px}
    @media (max-width: 640px){
      header h1{font-size:14px}
      .kv b{min-width:70px}
    }
  </style>
</head>
<body>
<header><h1>Logo Manager (subir/reemplazar logos por ID)</h1></header>
<main>
  <div class="card">
    <div class="stats" id="stats"></div>
    <div class="tabs">
      <button class="tab active" data-tab="search">Buscar / Subir</button>
      <button class="tab" data-tab="all">Todos los clubes</button>
      <button class="tab" data-tab="missing">Faltantes (sin logo)</button>
    </div>

    <div id="panel-search" class="panel">
      <div class="row">
        <div class="col">
          <label>Buscar club</label>
          <input id="q" type="text" placeholder="Ej: Belgrano Córdoba" autocomplete="off" />
          <div class="muted">Busca por nombre / ciudad / provincia. Elegí un resultado para subir el logo.</div>
          <div id="results" class="results" style="display:none"></div>
        </div>
        <div class="col">
          <label>Club seleccionado</label>
          <div class="preview">
            <img id="logo" class="logo" src="" alt="logo" style="display:none" />
            <div class="kv" id="clubkv"><span class="muted">Ninguno</span></div>
          </div>
          <div class="actions">
            <input id="file" type="file" accept="image/*" />
            <label style="display:flex;gap:8px;align-items:center;margin:0">
              <input id="regen" type="checkbox" checked />
              <span class="muted">Regenerar exports (clubs_data.*)</span>
            </label>
            <button id="upload" disabled>Subir y reemplazar</button>
          </div>
          <div class="status" id="status"></div>
        </div>
      </div>
    </div>

    <div id="panel-all" class="panel" style="display:none">
      <div class="list" id="list-all"></div>
    </div>

    <div id="panel-missing" class="panel" style="display:none">
      <div class="list" id="list-missing"></div>
    </div>
  </div>
</main>
<script>
  let selected = null;

  const q = document.getElementById('q');
  const results = document.getElementById('results');
  const clubkv = document.getElementById('clubkv');
  const logo = document.getElementById('logo');
  const file = document.getElementById('file');
  const uploadBtn = document.getElementById('upload');
  const statusEl = document.getElementById('status');
  const regenCb = document.getElementById('regen');

  function setStatus(msg) {
    statusEl.textContent = msg || '';
  }

  function renderSelected() {
    if (!selected) {
      clubkv.innerHTML = '<span class="muted">Ninguno</span>';
      logo.style.display = 'none';
      uploadBtn.disabled = true;
      return;
    }
    clubkv.innerHTML = `
      <div><b>ID</b> ${selected.id}</div>
      <div><b>Nombre</b> ${selected.nombre}</div>
      <div><b>Ciudad</b> ${selected.ciudad}</div>
      <div><b>Provincia</b> ${selected.provincia}</div>
      <div><b>División</b> ${selected.division}</div>
      <div style="margin-top:6px">
        <span class="badge ${selected.has_logo ? 'ok' : 'no'}">${selected.has_logo ? 'Tiene logo' : 'Sin logo'}</span>
      </div>
    `;

    logo.src = `/logos/${selected.id}.png?ts=${Date.now()}`;
    logo.style.display = 'block';
    logo.onerror = () => { logo.style.display = 'none'; };

    uploadBtn.disabled = !file.files || file.files.length === 0;
  }

  async function doSearch() {
    const value = q.value.trim();
    if (value.length < 2) {
      results.style.display = 'none';
      results.innerHTML = '';
      return;
    }
    const res = await fetch(`/api/search?q=${encodeURIComponent(value)}`);
    const data = await res.json();
    results.innerHTML = '';
    if (!data.items || data.items.length === 0) {
      results.style.display = 'none';
      return;
    }
    results.style.display = 'block';
    data.items.forEach(item => {
      const div = document.createElement('div');
      div.className = 'result';
      div.innerHTML = `
        <div style="flex:1">
          <div style="font-weight:700">${item.nombre}</div>
          <div class="muted">${item.ciudad}, ${item.provincia} · ID ${item.id}</div>
        </div>
        <span class="badge ${item.has_logo ? 'ok' : 'no'}">${item.has_logo ? 'Logo' : 'Sin'}</span>
      `;
      div.onclick = () => {
        selected = item;
        results.style.display = 'none';
        setStatus('');
        renderSelected();
      };
      results.appendChild(div);
    });
  }

  q.addEventListener('input', () => { doSearch().catch(() => {}); });
  file.addEventListener('change', () => { renderSelected(); });

  uploadBtn.addEventListener('click', async () => {
    if (!selected) return;
    if (!file.files || file.files.length === 0) return;

    setStatus('Subiendo...');
    uploadBtn.disabled = true;

    const form = new FormData();
    form.append('club_id', selected.id);
    form.append('regen', regenCb.checked ? '1' : '0');
    form.append('image', file.files[0]);

    const res = await fetch('/api/upload', { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok) {
      setStatus(data.error || 'Error');
      uploadBtn.disabled = false;
      return;
    }

    setStatus(data.message || 'OK');
    // refresh selection data
    const refresh = await fetch(`/api/club/${selected.id}`);
    const updated = await refresh.json();
    selected = updated.item;
    renderSelected();
    uploadBtn.disabled = false;
    loadStats();
  });

  renderSelected();

  // Tabs
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.style.display = 'none');
      tab.classList.add('active');
      document.getElementById('panel-' + tab.dataset.tab).style.display = 'block';
      if (tab.dataset.tab === 'all') loadAll();
      if (tab.dataset.tab === 'missing') loadMissing();
    });
  });

  async function loadStats() {
    const res = await fetch('/api/clubs');
    const data = await res.json();
    const items = data.items || [];
    const total = items.length;
    const withLogo = items.filter(c => c.has_logo).length;
    const without = total - withLogo;
    document.getElementById('stats').innerHTML = `
      <div class="stat"><b>${total}</b> Total</div>
      <div class="stat"><b>${withLogo}</b> Con logo</div>
      <div class="stat"><b>${without}</b> Sin logo</div>
    `;
  }
  loadStats();

  function renderList(containerId, items) {
    const el = document.getElementById(containerId);
    if (!items || items.length === 0) {
      el.innerHTML = '<div class="empty">No hay clubes para mostrar</div>';
      return;
    }
    el.innerHTML = items.map(c => `
      <div class="list-item" data-id="${c.id}">
        <img src="/logos/${c.id}.png" alt="" onerror="this.style.visibility='hidden'">
        <div class="info">
          <div class="name">${c.nombre}</div>
          <div class="meta">${c.ciudad}, ${c.provincia} · ID ${c.id} · ${c.division}</div>
        </div>
        <span class="badge ${c.has_logo ? 'ok' : 'no'}">${c.has_logo ? 'Logo' : 'Sin'}</span>
      </div>
    `).join('');
    el.querySelectorAll('.list-item').forEach(row => {
      row.addEventListener('click', async () => {
        const id = parseInt(row.dataset.id);
        const res = await fetch('/api/club/' + id);
        const data = await res.json();
        if (data.item) {
          selected = data.item;
          document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
          document.querySelectorAll('.panel').forEach(p => p.style.display = 'none');
          document.querySelector('[data-tab="search"]').classList.add('active');
          document.getElementById('panel-search').style.display = 'block';
          setStatus('');
          renderSelected();
          window.scrollTo({top:0,behavior:'smooth'});
        }
      });
    });
  }

  async function loadAll() {
    const res = await fetch('/api/clubs');
    const data = await res.json();
    renderList('list-all', data.items);
  }

  async function loadMissing() {
    const res = await fetch('/api/missing');
    const data = await res.json();
    renderList('list-missing', data.items);
  }
</script>
</body>
</html>
"""


@app.get("/")
def index() -> str:
    return render_template_string(HTML)


@app.get("/api/clubs")
def api_clubs() -> Response:
    items: list[dict[str, Any]] = []
    for c in CLUBS:
        items.append(
            {
                "id": c.id,
                "nombre": c.nombre,
                "ciudad": c.ciudad,
                "provincia": c.provincia,
                "division": c.division,
                "has_logo": bool(c.has_logo) or club_has_logo_file(c.id),
            }
        )
    return jsonify({"items": items})


@app.get("/api/missing")
def api_missing() -> Response:
    items: list[dict[str, Any]] = []
    for c in CLUBS:
        has = bool(c.has_logo) or club_has_logo_file(c.id)
        if not has:
            items.append(
                {
                    "id": c.id,
                    "nombre": c.nombre,
                    "ciudad": c.ciudad,
                    "provincia": c.provincia,
                    "division": c.division,
                    "has_logo": False,
                }
            )
    return jsonify({"items": items})


@app.get("/api/search")
def api_search() -> Response:
    q = (request.args.get("q") or "").strip()
    nq = normalize(q)

    if len(nq) < 2:
        return jsonify({"items": []})

    items: list[dict[str, Any]] = []

    for c in CLUBS:
        haystack = normalize(f"{c.nombre} {c.ciudad} {c.provincia} {c.ubicacion} {c.division}")
        if nq in haystack:
            items.append(
                {
                    "id": c.id,
                    "nombre": c.nombre,
                    "ciudad": c.ciudad,
                    "provincia": c.provincia,
                    "division": c.division,
                    "has_logo": bool(c.has_logo) or club_has_logo_file(c.id),
                }
            )
        if len(items) >= 20:
            break

    return jsonify({"items": items})


@app.get("/api/club/<int:club_id>")
def api_club(club_id: int) -> Response:
    for c in CLUBS:
        if c.id == club_id:
            return jsonify(
                {
                    "item": {
                        "id": c.id,
                        "nombre": c.nombre,
                        "ciudad": c.ciudad,
                        "provincia": c.provincia,
                        "division": c.division,
                        "has_logo": bool(c.has_logo) or club_has_logo_file(c.id),
                    }
                }
            )
    return jsonify({"error": "Club no encontrado"}), 404


@app.get("/logos/<path:filename>")
def get_logo(filename: str) -> Response:
    try:
        club_id = int(filename.split(".")[0])
    except Exception:
        return jsonify({"error": "Nombre inválido"}), 400

    p = logo_path(club_id)
    if not os.path.exists(p):
        p = docs_logo_path(club_id)

    if not os.path.exists(p):
        return jsonify({"error": "No existe"}), 404

    return send_file(p)


@app.post("/api/upload")
def api_upload() -> Response:
    ensure_dirs()

    club_id_raw = request.form.get("club_id")
    if not club_id_raw:
        return jsonify({"error": "Falta club_id"}), 400

    try:
        club_id = int(club_id_raw)
    except ValueError:
        return jsonify({"error": "club_id inválido"}), 400

    f = request.files.get("image")
    if f is None:
        return jsonify({"error": "Falta image"}), 400

    file_bytes = f.read()
    if not file_bytes:
        return jsonify({"error": "Archivo vacío"}), 400

    try:
        png_bytes = process_image_to_png(file_bytes)
    except Exception as e:
        return jsonify({"error": f"No pude procesar la imagen: {e}"}), 400

    out1 = logo_path(club_id)
    out2 = docs_logo_path(club_id)
    with open(out1, "wb") as o:
        o.write(png_bytes)
    with open(out2, "wb") as o:
        o.write(png_bytes)

    regen = (request.form.get("regen") or "").strip() == "1"
    msg = f"Guardado: LOGOS/{club_id}.png y docs/LOGOS/{club_id}.png"

    if regen:
        ok, out = run_extract_exports()
        if ok:
            msg += "\nExports regenerados (clubs_data.js / clubs_data.json)."
            msg += ("\n" + out) if out else ""
            load_clubs()
        else:
            return jsonify({"error": f"Logo guardado, pero falló regeneración de exports:\n{out}"}), 500

    return jsonify({"message": msg})


@app.get("/api/reload")
def api_reload() -> Response:
    load_clubs()
    return jsonify({"ok": True, "count": len(CLUBS)})


def main() -> None:
    ensure_dirs()
    load_clubs()
    app.run(host="127.0.0.1", port=5173, debug=True)


if __name__ == "__main__":
    main()
