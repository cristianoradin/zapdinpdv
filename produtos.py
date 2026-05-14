"""
produtos.py — Catálogo de produtos do PDV.
Armazenado em data/produtos.json (editável pelo painel).
"""
import json
import uuid
from pathlib import Path
from typing import List, Optional

_DATA_FILE = Path(__file__).parent / "data" / "produtos.json"


def _load() -> dict:
    try:
        return json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"produtos": []}


def _save(data: dict) -> None:
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def listar() -> List[dict]:
    return _load().get("produtos", [])


def buscar(produto_id: str) -> Optional[dict]:
    return next((p for p in listar() if p["id"] == produto_id), None)


def salvar(produto: dict) -> dict:
    data = _load()
    produtos = data.get("produtos", [])
    idx = next((i for i, p in enumerate(produtos) if p["id"] == produto.get("id")), None)
    if idx is not None:
        produtos[idx] = produto
    else:
        produto.setdefault("id", str(uuid.uuid4())[:6])
        produtos.append(produto)
    data["produtos"] = produtos
    _save(data)
    return produto


def deletar(produto_id: str) -> bool:
    data = _load()
    antes = len(data.get("produtos", []))
    data["produtos"] = [p for p in data.get("produtos", []) if p["id"] != produto_id]
    _save(data)
    return len(data["produtos"]) < antes


def categorias() -> List[str]:
    todas = {p.get("categoria", "Geral") for p in listar()}
    return sorted(todas)
