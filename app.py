import json
import streamlit as st
from youtube_search import YoutubeSearch
from github import Github, GithubException

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="5. Sınıf Video Kütüphanesi",
    page_icon="🎬",
    layout="wide"
)

# --- MODERN KART TASARIMI (CSS) ---
st.markdown("""
<style>
    .badge {
        background-color: #ff4b4b;
        color: white;
        padding: 3px 9px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .note-box {
        background-color: rgba(255, 193, 7, 0.12);
        border-left: 3px solid #ffc107;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 13px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- 2026-2027 MEB 5. SINIF MÜFREDATI ---
MUFREDAT = {
    "Fen Bilimleri": {
        "1. Gökyüzündeki Komşularımız ve Biz": ["Güneş'in Yapısı ve Dönme Hareketi", "Ay'ın Özellikleri ve Evreleri", "Güneş, Dünya ve Ay Modeli"],
        "2. Kuvveti Tanıyalım": ["Kuvvetin Ölçülmesi ve Dinamometre", "Kütle ve Ağırlık İlişkisi", "Sürtünme Kuvveti"],
        "3. Canlıların Yapısına Yolculuk": ["Hücre ve Organelleri", "Bitki ve Hayvan Hücresi Farkları", "Destek ve Hareket Sistemi"],
        "4. Işığın Dünyası": ["Işığın Yayılması", "Maddenin Işık Geçirgenliği", "Tam Gölgenin Oluşumu"],
        "5. Maddenin Doğası": ["Maddenin Tanecikli Yapısı", "Isı ve Sıcaklık", "Maddenin Hâl Değişimi", "Isı İletimi ve Yalıtımı"],
        "6. Yaşamımızdaki Elektrik": ["Devre Elemanlarının Sembolleri", "Ampul Parlaklığını Etkileyen Değişkenler"],
        "7. Sürdürülebilir Yaşam ve Geri Dönüşüm": ["Evsel Atıklar ve Geri Dönüşüm"]
    },
    "Matematik": {
        "1. Geometrik Şekiller": ["Temel Geometrik Çizimler", "Açı Ölçme", "Çokgenler ve Çember"],
        "2. Sayılar ve Nicelikler (1)": ["Çok Basamaklı Doğal Sayılar", "Doğal Sayılarla İşlemler ve Problemler"],
        "3. Geometrik Nicelikler": ["Dikdörtgenin Çevre Uzunluğu", "Dikdörtgenin Alanı"],
        "4. Sayılar ve Nicelikler (2)": ["Kesirler ve Karşılaştırma", "Ondalık Gösterim", "Yüzdeler"],
        "5. İstatistiksel Araştırma Süreci": ["Veri Toplama ve Tablolama", "Sütun ve Çizgi Grafikleri"],
        "6. İşlemlerle Cebirsel Düşünme": ["Eşitliğin Korunumu", "İşlem Önceliği", "Örüntüler ve Algoritma"],
        "7. Veriden Olasılığa": ["Kesin ve İmkânsız Olaylar", "Olasılık Spektrumu"]
    }
}

FILE_PATH = "data/saved_videos.json"

# --- GITHUB İŞLEMLERİ ---
def get_github_repo():
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["GITHUB_REPO"]
    g = Github(token)
    return g.get_repo(repo_name)

@st.cache_data(ttl=60)
def load_saved_videos():
    try:
        repo = get_github_repo()
        contents = repo.get_contents(FILE_PATH)
        return json.loads(contents.decoded_content.decode("utf-8")), contents.sha
    except GithubException:
        return [], None
    except Exception as e:
        st.error(f"GitHub bağlantı hatası: {e}")
        return [], None

def save_video_to_github(video_data):
    repo = get_github_repo()
    videos, sha = load_saved_videos()
    if any(v["id"] == video_data["id"] for v in videos):
        st.toast("⚠️ Bu video zaten kütüphanede kayıtlı!", icon="ℹ️")
        return

    videos.append(video_data)
    updated_content = json.dumps(videos, ensure_ascii=False, indent=2)
    if sha:
        repo.update_file(FILE_PATH, f"Video eklendi: {video_data['title'][:30]}", updated_content, sha)
    else:
        repo.create_file(FILE_PATH, "İlk video kaydı oluşturuldu", updated_content)
    st.cache_data.clear()
    st.toast("✅ Video GitHub deposuna kaydedildi!", icon="🎉")

def delete_video_from_github(video_id):
    repo = get_github_repo()
    videos, sha = load_saved_videos()
    videos = [v for v in videos if v["id"] != video_id]
    updated_content = json.dumps(videos, ensure_ascii=False, indent=2)
    repo.update_file(FILE_PATH, f"Video silindi: {video_id}", updated_content, sha)
    st.cache_data.clear()
    st.rerun()

def search_youtube(query, max_results=6):
    try:
        return YoutubeSearch(query, max_results=max_results).to_dict()
    except Exception as e:
        st.error(f"Arama sırasında hata oluştu: {e}")
        return []

# --- YAN MENÜ ---
with st.sidebar:
    st.title("📚 Ders & Konu Seçimi")
    ders = st.selectbox("Ders", list(MUFREDAT.keys()))
    unite = st.selectbox("Ünite / Tema", list(MUFREDAT[ders].keys()))
    konu = st.selectbox("Konu", MUFREDAT[ders][unite])
    
    st.divider()
    ekstra_kelime = st.text_input("Arama Filtresi", value="konu anlatımı")
    sonuc_sayisi = st.slider("Video Sayısı", 4, 12, 6)
    ara_btn = st.button("🔍 YouTube'da Ara", type="primary", use_container_width=True)

# --- ANA EKRAN ---
st.title("🎓 5. Sınıf Akıllı Video Havuzu")
st.caption(f"Aktif Konu: **{ders}** ➔ **{unite}** ➔ **{konu}**")

tab_ara, tab_kayitli = st.tabs(["🔎 Video Ara & Keşfet", "💾 GitHub Video Kütüphanesi"])

# 1. SEKME: YOUTUBE ARAMA & BENZER VİDEO BULMA
with tab_ara:
    if ara_btn:
        sorgu = f"5. sınıf {ders} {konu} {ekstra_kelime}".strip()
        with st.spinner(f"'{sorgu}' aranıyor..."):
            st.session_state["search_results"] = search_youtube(sorgu, sonuc_sayisi)
            st.session_state["active_query"] = sorgu
            st.session_state["last_meta"] = {"ders": ders, "unite": unite, "konu": konu}

    if "search_results" in st.session_state:
        results = st.session_state["search_results"]
        meta = st.session_state.get("last_meta", {"ders": ders, "unite": unite, "konu": konu})
        st.info(f"Gösterilen arama: **{st.session_state.get('active_query', '')}**")

        if not results:
            st.warning("Sonuç bulunamadı. Arama filtresini değiştirip tekrar deneyin.")
        else:
            cols = st.columns(2)
            for idx, item in enumerate(results):
                video_url = f"https://www.youtube.com/watch?v={item['id']}"
                with cols[idx % 2]:
                    with st.container(border=True):
                        st.video(video_url)
                        st.markdown(f"**{item['title']}**")
                        st.caption(f"📺 {item['channel']} • ⏱️ {item['duration']} • 👁️ {item['views']}")
                        
                        not_metni = st.text_input("Kısa Not (Opsiyonel)", key=f"note_{item['id']}", placeholder="Örn: Sınav öncesi izlenecek...")
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("⭐ Kaydet", key=f"save_{item['id']}", use_container_width=True):
                                record = {
                                    "id": item["id"],
                                    "title": item["title"],
                                    "channel": item["channel"],
                                    "duration": item["duration"],
                                    "url": video_url,
                                    "ders": meta["ders"],
                                    "unite": meta["unite"],
                                    "konu": meta["konu"],
                                    "not": not_metni
                                }
                                save_video_to_github(record)
                        with c2:
                            if st.button("🔄 Benzerlerini Bul", key=f"sim_{item['id']}", use_container_width=True):
                                benzer_sorgu = f"5. sınıf {item['title'][:45]}"
                                with st.spinner("Benzer videolar getiriliyor..."):
                                    st.session_state["search_results"] = search_youtube(benzer_sorgu, sonuc_sayisi)
                                    st.session_state["active_query"] = f"Benzeri: {item['title'][:40]}..."
                                    st.rerun()

# 2. SEKME: GITHUB KÜTÜPHANESİ
with tab_kayitli:
    saved_videos, _ = load_saved_videos()
    if not saved_videos:
        st.info("Henüz GitHub deposuna kaydedilmiş video yok. İlk sekmeden video kaydedebilirsiniz.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtre_ders = st.selectbox("Derse Göre Filtrele", ["Tümü"] + list(MUFREDAT.keys()))
        with col_f2:
            konular = sorted(list({v["konu"] for v in saved_videos if filtre_ders == "Tümü" or v["ders"] == filtre_ders}))
            filtre_konu = st.selectbox("Konuya Göre Filtrele", ["Tümü"] + konular)

        filtrelenmis = [
            v for v in saved_videos
            if (filtre_ders == "Tümü" or v["ders"] == filtre_ders)
            and (filtre_konu == "Tümü" or v["konu"] == filtre_konu)
        ]

        st.write(f"Toplam **{len(filtrelenmis)}** kayıtlı video listeleniyor.")
        cols = st.columns(2)
        for idx, vid in enumerate(filtrelenmis):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.markdown(f"<span class='badge'>{vid['ders']}</span> • **{vid['konu']}**", unsafe_allow_html=True)
                    st.video(vid["url"])
                    st.markdown(f"**{vid['title']}**")
                    st.caption(f"📺 {vid['channel']} • ⏱️ {vid['duration']}")
                    if vid.get("not"):
                        st.markdown(f"<div class='note-box'>📝 <b>Not:</b> {vid['not']}</div>", unsafe_allow_html=True)
                    if st.button("🗑️ Kütüphaneden Sil", key=f"del_{vid['id']}", use_container_width=True):
                        delete_video_from_github(vid["id"])
