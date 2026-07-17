# ui/app.py
import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://api:8000")
LOGO_URL = "https://bau.edu.tr/assets/brand/bau/bau-logo-white-horizontal.svg"

NAVY = "#01265A"
CYAN = "#00ADEF"

st.set_page_config(
    page_title="BAU Öğrenci İşleri Asistanı",
    page_icon="🎓",
    layout="centered",
)

st.markdown(
    f"""
    <style>
    #MainMenu, footer, header {{ visibility: hidden; }}

    .stApp {{
        background: linear-gradient(135deg, {NAVY} 0%, #03224f 45%, {CYAN} 100%);
        background-attachment: fixed;
        overflow: hidden;
    }}

    /* Hareketli, blur'lu ışık blob'ları — Liquid Glass'ın arkadaki "canlı" katmanı */
    .stApp::before, .stApp::after {{
        content: "";
        position: fixed;
        border-radius: 50%;
        filter: blur(90px);
        z-index: 0;
        opacity: 0.55;
    }}
    .stApp::before {{
        width: 480px; height: 480px;
        background: {CYAN};
        top: -120px; left: -100px;
        animation: float-a 18s ease-in-out infinite;
    }}
    .stApp::after {{
        width: 420px; height: 420px;
        background: #4949FF;
        bottom: -140px; right: -80px;
        animation: float-b 22s ease-in-out infinite;
    }}
    @keyframes float-a {{
        0%, 100% {{ transform: translate(0, 0) scale(1); }}
        50% {{ transform: translate(60px, 80px) scale(1.15); }}
    }}
    @keyframes float-b {{
        0%, 100% {{ transform: translate(0, 0) scale(1); }}
        50% {{ transform: translate(-50px, -60px) scale(1.1); }}
    }}

    .block-container {{
        position: relative;
        z-index: 1;
        max-width: 720px;
        padding-top: 2rem;
    }}

    .glass-header {{
        background: rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 28px;
        padding: 1.75rem 2rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
        margin-bottom: 1.5rem;
    }}
    .glass-header img {{ height: 42px; margin-bottom: 0.75rem; }}
    .glass-header h1 {{
        color: #fff;
        font-size: 1.3rem;
        font-weight: 600;
        margin: 0;
    }}
    .glass-header p {{
        color: rgba(255, 255, 255, 0.75);
        font-size: 0.85rem;
        margin: 0.25rem 0 0 0;
    }}

    [data-testid="stChatMessage"] {{
        background: rgba(255, 255, 255, 0.14) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 22px !important;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.2);
        margin-bottom: 0.75rem;
    }}
    [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] span {{
        color: #fff !important;
    }}

    [data-testid="stChatInput"] {{
        background: rgba(255, 255, 255, 0.14);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 999px !important;
    }}
    [data-testid="stChatInput"] textarea {{
        color: #fff !important;
    }}

    .source-box {{
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 16px;
        padding: 0.6rem 1rem;
        margin-top: -0.4rem;
        margin-bottom: 0.75rem;
        font-size: 0.8rem;
        color: rgba(255, 255, 255, 0.8);
    }}
    </style>

    <div class="glass-header">
        <img src="{LOGO_URL}" alt="BAU logo" />
        <h1>BAU Öğrenci İşleri Asistanı</h1>
        <p>Personel kullanımı içindir · Cevaplar kurum içi doküman kaynaklıdır</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []


def format_sources(sources: list[dict]) -> str:
    lines = []
    for s in sources:
        line = f"**{s['section_title']}** bölümü (sayfa {s['page']})"
        if s.get("link_url"):
            label = s.get("link_label") or "detaylar"
            line += f" — {label} için: {s['link_url']}"
        lines.append(line)
    return "  \n".join(lines)


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            st.markdown(
                f'<div class="source-box">📎 {format_sources(message["sources"])}</div>',
                unsafe_allow_html=True,
            )

question = st.chat_input("Bir soru sor...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Aranıyor..."):
            try:
                response = requests.post(f"{API_URL}/query", json={"question": question}, timeout=30)
                response.raise_for_status()
                data = response.json()
                answer = data["answer"]
                sources = data["sources"]
            except requests.RequestException as e:
                answer = f"Sunucuya bağlanılamadı: {e}"
                sources = []

        st.markdown(answer)
        if sources:
            st.markdown(
                f'<div class="source-box">📎 {format_sources(sources)}</div>',
                unsafe_allow_html=True,
            )

    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
