# BAU Öğrenci İşleri Asistanı — Proje Brief

Bu dosya, Claude Code'un bu proje üzerinde çalışırken uyması gereken çalışma tarzını ve projenin tam teknik scope'unu içerir. Kod yazmaya başlamadan önce bu dosyayı oku.

---

## Çalışma Tarzı (ÖNEMLİ — her adımda uygula)

- **Otonom ilerleme yok.** Kodu sen yazıp doğrudan çalıştırma/deploy etme — kullanıcı kodu kendi yapıştıracak.
- **Her adımı öğreterek anlat.** Bir dosya/fonksiyon yazmadan önce: ne yapılacağını, neden bu şekilde yapıldığını, hangi kararların alındığını kısaca açıkla. Sonra kodu ver.
- **Faz faz ilerle, onay bekle.** Tüm projeyi tek seferde dökme — bir adımı tamamla (örn. sadece `ingest.py`), kullanıcının onayını/geri bildirimini bekle, sonra bir sonraki adıma geç.
- **Kod bloklarını kullanıcı kendi yapıştıracak.** Dosya oluşturma/düzenleme işlemini otomatik yapma, kodu chat'te ver.
- **Kısa problem tanımı + kod tercih edilir**, uzun uzadıya anlatım yerine. Ama "neden" kısmını atlama — kullanıcı mühendislik kararlarını anlayarak ilerlemek istiyor, kopyala-yapıştır yapmak değil.
- Varsayım yapman gerekirse belirt ve ilerle; gereksiz yere çok soru sorup akışı yavaşlatma.

---

## Proje Amacı

Bahçeşehir Üniversitesi öğrenci işleri **çalışanlarının** (öğrencilerin değil) kullanacağı bir soru-cevap asistanı. Sistem, embed edilmiş kurum içi dokümana dayanarak cevap üretir, context dışında bir şey uydurmaz, ve her cevabın altında hangi bölümden geldiğini ve varsa ilgili linki kaynak olarak gösterir. Doğruluk ve "bilmiyorum" diyebilme akıcılıktan daha önemli — çünkü hedef kitle personel, yanlış prosedür bilgisi gerçek sonuç doğurur.

MVP aşamasındayız, demo yakın zamanda yapılacak.

---

## Veri İşleme Akışı

1. **Student_Guidebook.pdf** → Ekstra OCR/vision-LLM katmanına gerek yok. İçerik zaten temizlenip section bazlı, tablo yapısı korunmuş bir markdown dosyasına (`guidebook_clean.md`) çevrildi.
2. **BAU_Student_Handbook_Data.docx** → **Embed edilmiyor.** Sadece `docx2python` ile section başlığı → hyperlink URL eşleşmesi (lookup sözlüğü, `links_lookup.json`) çıkarılacak. QR kod decode'una gerek yok çünkü QR'lar zaten docx'teki linklerle aynı hedefe gidiyor.
3. Temizlenmiş markdown, `##` başlıklarına göre section bazlı chunk'lara bölünecek. Her chunk'a, `links_lookup.json`'dan ilgili section'ın linki (varsa) metadata olarak eklenecek.

### Chunk Şeması

```json
{
  "section_title": "Scholarships",
  "page": 13,
  "body_markdown": "- Success Scholarship: ...",
  "link": {"label": "BAU Scholarships", "url": "https://..."}
}
```

### Generation Davranış Kuralı

- Sadece retrieve edilen context'ten cevap ver. Context'te yoksa açıkça "bu bilgi elimde yok" de.
- Chunk'ın `link` alanı doluysa, linki çıplak URL olarak basma — linkin ne ile ilgili olduğunu bir cümlede söyleyip ("burs detayları için", "form başvurusu için" gibi) sonra linki ver.
- Cevabın altında kaynak olarak section adı + sayfa numarası (+ varsa link) gösterilecek.

Örnek çıktı:
> **Cevap:** 4. dönemin sonunda, bölümünde 1. veya 2. olan öğrenciler bir sonraki yıl için %100 veya %50 burs alır.
> **Kaynak:** Scholarships bölümü (sayfa 13) — burs detayları için: `https://...`

---

## Stack

Docker zorunlu ve ekip arkadaşı bunu kendi localinde `docker-compose up` ile ayağa kaldıracak — bu yüzden minimum bağımlılıklı, tek komutla çalışan bir yapı hedefleniyor.

| Katman | Seçim | Neden |
|---|---|---|
| Backend | Python + **FastAPI** | Retrieval + generation endpoint'i için hafif, dockerize etmesi kolay |
| Vector store | **Chroma** (embedded, local persist) | Ayrı bir DB container'ı gerekmiyor, dosya bazlı persist ediyor — corpus küçük olduğu için ayrı bir vector DB servisi gereksiz kompleksite |
| Embedding + Generation | OpenAI API veya Anthropic API (kullanıcının elindeki key'e göre) | Mimari aynı, sadece `.env`'de model adı değişir |
| Frontend | **Streamlit** | Chat arayüzü + source gösterimi için en az kod, tek satırla dockerize edilir |
| Container yapısı | `docker-compose.yml` içinde 2 servis: `api` ve `ui` | Ayrım net: biri mantık, biri arayüz |

## Klasör Yapısı

```
bau-assistant/
├── docker-compose.yml
├── api/
│   ├── Dockerfile
│   ├── main.py              # FastAPI: /query endpoint
│   ├── ingest.py            # chunk'la + embed et + Chroma'ya yaz (bir kerelik, idempotent)
│   ├── data/
│   │   ├── guidebook_clean.md
│   │   └── links_lookup.json
│   └── chroma_db/            # persisted volume
├── ui/
│   ├── Dockerfile
│   └── app.py                # Streamlit chat arayüzü
└── .env                       # API key'ler
```

## Runtime Akışı

1. Container ilk ayağa kalktığında `ingest.py` çalışır (Chroma boşsa): markdown'ı chunk'lar, `links_lookup.json`'dan ilgili linki eşler, embed edip Chroma'ya yazar. İdempotent olmalı — Chroma doluysa tekrar çalışmamalı.
2. Kullanıcı Streamlit arayüzünden soru sorar.
3. UI, FastAPI'nin `/query` endpoint'ine soruyu gönderir.
4. API: top-k (3-5) chunk retrieve eder → prompt'a context olarak koyar → generation model'e gönderir.
5. Cevap + kaynak UI'da gösterilir.

## Docker Gereksinimleri

- `docker-compose.yml`: `api` ve `ui` servisleri, aralarında internal network, `api` için Chroma volume mount'u (`./api/chroma_db:/app/chroma_db`), `.env`'den API key inject.
- Tek komutla ayağa kalkmalı: `docker-compose up --build`. Ekip arkadaşının yapması gereken tek şey `.env` dosyasına kendi API key'ini koymak.

## Sırada Ne Var (bu sırayla, faz faz ilerlenecek)

1. `ingest.py` — chunking + `docx2python` link lookup + Chroma embed
2. `main.py` — FastAPI query endpoint + prompt template
3. `app.py` — Streamlit arayüz
4. `Dockerfile`'lar + `docker-compose.yml`

Her adımdan sonra kullanıcı kodu kendi projesine yapıştırıp test edecek, geri bildirim verecek, onay sonrası bir sonraki adıma geçilecek.
