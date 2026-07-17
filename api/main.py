# api/main.py
"""
FastAPI /query endpoint: embeds the user's question, retrieves the most relevant
sections from Chroma, passes them to the generation model as context, and
returns the generated answer along with its sources.
"""

import os

import chromadb
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel

CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", "chroma_db")
COLLECTION_NAME = "guidebook"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

GENERATION_PROVIDER = os.environ.get("GENERATION_PROVIDER", "openai")  # "openai" | "anthropic"
GENERATION_MODEL = os.environ.get(
    "GENERATION_MODEL",
    "gpt-4o-mini" if GENERATION_PROVIDER == "openai" else "claude-haiku-4-5",
)
TOP_K = int(os.environ.get("TOP_K", "4"))

UNKNOWN_MARKER = "bu bilgi elimde yok"
SOURCE_MARKER = "[KAYNAK_VAR]"

SMALL_TALK_KEYWORDS = [
    "selam", "merhaba", "naber", "günaydın", "iyi günler", "iyi akşamlar",
    "teşekkür", "sağol", "sağ ol", "görüşürüz", "hoşça kal", "hi", "hello", "hey",
]


def is_small_talk(question: str) -> bool:
    q = question.strip().lower()
    return len(q.split()) <= 4 and any(kw in q for kw in SMALL_TALK_KEYWORDS)



SYSTEM_PROMPT = """Sen Bahçeşehir Üniversitesi öğrenci işleri çalışanları için bir iç bilgi asistanısın.
Sana verilen BAĞLAM dışında hiçbir bilgi kullanma, tahmin yürütme veya uydurma yapma.

Kurallar:
- Kullanıcı selamlama, teşekkür veya kendini tanıtma isteği gibi genel bir sohbet ifadesi kullanıyorsa, BAĞLAM'a bakmadan kısa ve nazik bir karşılık ver.
- Kullanıcı üniversite prosedürü/bilgisiyle ilgili gerçek bir soru soruyorsa, sadece aşağıdaki BAĞLAM içindeki bilgiye dayanarak cevap ver. BAĞLAM'da bilgi yoksa, başka hiçbir şey eklemeden sadece şunu yaz: "Bu bilgi elimde yok."
- Cevabını kısa ve net ver. Kaynak, sayfa numarası veya link ekleme — bunlar ayrıca sistem tarafından gösterilecek.
- Cevabın BAĞLAM'daki spesifik bir bilgiye (bir kural, sayı, prosedür, isim vb.) gerçekten dayanıyorsa, cevabının en sonuna yeni bir satırda tam olarak şunu ekle: [KAYNAK_VAR]
  Cevabın bir sohbet karşılığıysa, kendini tanıtmaysa veya "Bu bilgi elimde yok" ise, bu etiketi kesinlikle ekleme.
"""


app = FastAPI()
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
openai_client = OpenAI() 


class QueryRequest(BaseModel):
    question: str


class Source(BaseModel):
    section_title: str
    page: str
    link_label: str | None = None
    link_url: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]


def embed_query(question: str) -> list[float]:
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=[question])
    return response.data[0].embedding


def retrieve(question: str) -> tuple[list[str], list[dict]]:
    query_embedding = embed_query(question)
    result = collection.query(query_embeddings=[query_embedding], n_results=TOP_K)
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    return documents, metadatas


def build_context(documents: list[str], metadatas: list[dict]) -> str:
    blocks = [
        f"### {meta['section_title']} (sayfa {meta['page']})\n{doc}"
        for doc, meta in zip(documents, metadatas)
    ]
    return "\n\n".join(blocks)


def generate_answer(question: str, context: str) -> str:
    user_message = f"BAĞLAM:\n{context}\n\nSORU: {question}"

    if GENERATION_PROVIDER == "openai":
        response = openai_client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content.strip()

    if GENERATION_PROVIDER == "anthropic":
        from anthropic import Anthropic

        anthropic_client = Anthropic()
        response = anthropic_client.messages.create(
            model=GENERATION_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text.strip()

    raise ValueError(f"Bilinmeyen GENERATION_PROVIDER: {GENERATION_PROVIDER}")


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    if collection.count() == 0:
        raise HTTPException(status_code=503, detail="Chroma boş — önce ingest.py çalıştırılmalı.")

    if is_small_talk(request.question):
        answer = generate_answer(request.question, context="")
        return QueryResponse(answer=answer, sources=[])

    documents, metadatas = retrieve(request.question)
    context = build_context(documents, metadatas)
    raw_answer = generate_answer(request.question, context)

    has_source_marker = SOURCE_MARKER in raw_answer
    answer = raw_answer.replace(SOURCE_MARKER, "").strip()
    is_unknown = UNKNOWN_MARKER in answer.lower()

    sources = [] if (is_unknown or not has_source_marker) else [
        Source(
            section_title=meta["section_title"],
            page=meta["page"],
            link_label=meta["link_label"] or None,
            link_url=meta["link_url"] or None,
        )
        for meta in metadatas
    ]

    return QueryResponse(answer=answer, sources=sources)

