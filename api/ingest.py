"""
Splits the guidebook Markdown into section-based chunks, matches each chunk
with the relevant link from links_lookup.json, embeds the chunks, and stores
them in Chroma. Idempotent: exits without making any changes if Chroma is
already populated.
"""


import json
import os
import re
from pathlib import Path

import chromadb
from openai import OpenAI

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
GUIDEBOOK_PATH = DATA_DIR / "guidebook_clean.md"
LINKS_PATH = DATA_DIR / "links_lookup.json"

CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", "chroma_db")
COLLECTION_NAME = "guidebook"

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

# Section başlığını yakalar: "## Scholarships"
SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)
# Başlığın hemen altındaki sayfa satırını yakalar: "(page: 13)" veya "(page: 2-3)"
PAGE_RE = re.compile(r"^\(page:\s*([^)]+)\)\s*\n?", re.MULTILINE)


def parse_guidebook(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")

    matches = list(SECTION_RE.finditer(text))
    chunks = []

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]

        page_match = PAGE_RE.match(body.strip())
        if page_match:
            page = page_match.group(1).strip()
            body = body[page_match.end():] if body.strip().startswith(page_match.group(0).strip()) else body
        else:
            page = None

        # page satırını body'den güvenli şekilde çıkar
        body_wo_page = PAGE_RE.sub("", body, count=1).strip()

        chunks.append({
            "section_title": title,
            "page": page,
            "body_markdown": body_wo_page,
        })

    return chunks


def load_links(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_chunks() -> list[dict]:
    sections = parse_guidebook(GUIDEBOOK_PATH)
    links = load_links(LINKS_PATH)

    for chunk in sections:
        chunk["link"] = links.get(chunk["section_title"])  # yoksa None

    return sections


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def run():
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = chroma_client.get_or_create_collection(COLLECTION_NAME)

    if collection.count() > 0:
        print(f"'{COLLECTION_NAME}' zaten dolu ({collection.count()} chunk) — ingest atlanıyor.")
        return

    chunks = build_chunks()
    print(f"{len(chunks)} section bulundu, embedding başlıyor...")

    openai_client = OpenAI()  # OPENAI_API_KEY env'den okunur
    texts = [f"{c['section_title']}\n{c['body_markdown']}" for c in chunks]
    embeddings = embed_texts(openai_client, texts)

    ids = [slugify(c["section_title"]) for c in chunks]
    documents = [c["body_markdown"] for c in chunks]
    metadatas = [
        {
            "section_title": c["section_title"],
            "page": c["page"] or "",
            "link_label": (c["link"] or {}).get("label", ""),
            "link_url": (c["link"] or {}).get("url", ""),
        }
        for c in chunks
    ]

    collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
    print(f"{len(chunks)} chunk Chroma'ya yazıldı.")


if __name__ == "__main__":
    run()
