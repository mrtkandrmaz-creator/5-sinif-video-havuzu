import os
import subprocess
import tempfile
import difflib
import cv2
import numpy as np
import streamlit as st
from skimage.metrics import structural_similarity as ssim
from faster_whisper import WhisperModel
from moviepy import VideoFileClip, concatenate_videoclips, vfx, afx

# Sayfa Ayarları
st.set_page_config(page_title="Akıllı Ders Videosu Birleştirici", page_icon="🎬", layout="wide")

st.title("🎬 Akıllı Ders Videosu Analiz & Birleştirme Aracı")
st.markdown("""
Aynı dersten çekilmiş birden fazla videoyu yükleyin. Yapay zeka **konuşmaları (Whisper)** ve **ekrandaki slaytları (OpenCV)** 
analiz ederek tekrarlayan anlatımları temizler, en detaylı bölümleri seçer ve yumuşak geçişlerle tek video haline getirir.
""")

# Yan Menü (Ayarlar)
with st.sidebar:
    st.header("⚙️ Analiz Ayarları")
    model_boyutu = st.selectbox(
        "Whisper Model Boyutu",
        options=["tiny", "base", "small", "medium"],
        index=2,
        help="Küçük modeller daha hızlıdır, büyük modeller Türkçe kelimeleri daha doğru anlar."
    )
    metin_esigi = st.slider("Konuşma Benzerlik Eşiği", 0.40, 0.95, 0.65, 0.05)
    goruntu_esigi = st.slider("Slayt/Ekran Benzerlik Eşiği", 0.60, 0.98, 0.85, 0.02)
    gecis_suresi = st.slider("Geçiş (Crossfade) Süresi (sn)", 0.0, 1.0, 0.4, 0.1)

@st.cache_resource
def model_yukle(boyut):
    return WhisperModel(boyut, device="cpu", compute_type="int8")

def sesi_wav_olarak_cikar(video_yolu, wav_yolu):
    """PyAV/Python 3.14 TypeError hatasını önlemek için sesi FFmpeg ile temiz WAV formatına çıkarır."""
    komut = [
        "ffmpeg", "-y", "-i", str(video_yolu),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(wav_yolu)
    ]
    subprocess.run(komut, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def kare_al(video_yolu, saniye):
    cap = cv2.VideoCapture(str(video_yolu))
    cap.set(cv2.CAP_PROP_POS_MSEC, saniye * 1000)
    ret, kare = cap.read()
    cap.release()
    if not ret:
        return None
    gri = cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gri, (320, 180))

def goruntu_benzerligi(kare1, kare2):
    if kare1 is None or kare2 is None:
        return 0.0
    skor, _ = ssim(kare1, kare2, full=True)
    return skor

# Dosya Yükleme Alanı
yuklenen_dosyalar = st.file_uploader(
    "Ders videolarını seçin (MP4, MOV, MKV)",
    type=["mp4", "mov", "mkv"],
    accept_multiple_files=True
)

if yuklenen_dosyalar:
    st.info(f"Toplam **{len(yuklenen_dosyalar)}** video yüklendi.")
    
    if st.button("🚀 Analiz Et ve Tek Video Oluştur", type="primary"):
        if len(yuklenen_dosyalar) < 2:
            st.warning("Karşılaştırma ve birleştirme için en az 2 video yüklemeniz önerilir.")
        
        ilerleme_cubugu = st.progress(0)
        durum_metni = st.empty()
        
        with tempfile.TemporaryDirectory() as gecici_dizin:
            video_yollari = []
            
            # 1. Yüklenen videoları geçici klasöre kaydet
            durum_metni.text("Videolar hazırlanıyor...")
            for idx, dosya in enumerate(yuklenen_dosyalar):
                # Türkçe karakter veya boşluk sorunlarını önlemek için güvenli isimlendirme
                uzanti = os.path.splitext(dosya.name)[1]
                guvenli_ad = f"video_{idx}_{dosya.name}"
                yol = os.path.join(gecici_dizin, guvenli_ad)
                with open(yol, "wb") as f:
                    f.write(dosya.getbuffer())
                video_yollari.append((yol, dosya.name))
            
            ilerleme_cubugu.progress(15)
            
            # 2. Whisper Modelini Yükle ve Ses + Slayt Analizi Yap
            durum_metni.text(f"Yapay zeka modeli ({model_boyutu}) yükleniyor...")
            model = model_yukle(model_boyutu)
            
            tum_segmentler = []
            toplam_video = len(video_yollari)
            
            for idx, (v_yol, orijinal_ad) in enumerate(video_yollari):
                durum_metni.text(f"Analiz ediliyor ({idx+1}/{toplam_video}): {orijinal_ad}...")
                
                # Sesi WAV olarak çıkar (av.open TypeError hatasını çözer)
                wav_yolu = os.path.join(gecici_dizin, f"ses_{idx}.wav")
                try:
                    sesi_wav_olarak_cikar(v_yol, wav_yolu)
                except Exception as e:
                    st.error(f"'{orijinal_ad}' dosyasının sesi okunamadı. Dosyada ses kanalı olduğundan emin olun.")
                    st.stop()
                
                segments, _ = model.transcribe(wav_yolu, language="tr")
                for seg in segments:
                    metin = seg.text.strip()
                    if len(metin) > 3:
                        orta_sn = (seg.start + seg.end) / 2
                        kare = kare_al(v_yol, orta_sn)
                        tum_segmentler.append({
                            "video": v_yol,
                            "dosya_adi": orijinal_ad,
                            "baslangic": seg.start,
                            "bitis": seg.end,
                            "metin": metin,
                            "kare": kare
                        })
                
                ilerleme_cubugu.progress(15 + int(45 * ((idx + 1) / toplam_video)))
            
            # 3. Benzerlik ve Tekrar Filtreleme
            durum_metni.text("Tekrarlayan slaytlar ve cümleler ayıklanıyor...")
            secilen_segmentler = []
            
            for aday in tum_segmentler:
                tekrar_bulundu = False
                for mevcut in secilen_segmentler:
                    metin_skoru = difflib.SequenceMatcher(None, aday["metin"].lower(), mevcut["metin"].lower()).ratio()
                    slayt_skoru = goruntu_benzerligi(aday["kare"], mevcut["kare"])
                    
                    ayni_slayt_ve_konu = (slayt_skoru >= goruntu_esigi) and (metin_skoru >= 0.45)
                    birebir_ayni_cumle = (metin_skoru >= metin_esigi)
                    
                    if ayni_slayt_ve_konu or birebir_ayni_cumle:
                        tekrar_bulundu = True
                        if len(aday["metin"]) > len(mevcut["metin"]):
                            mevcut.update(aday)
                        break
                
                if not tekrar_bulundu:
                    secilen_segmentler.append(aday)
            
            ilerleme_cubugu.progress(70)
            
            if not secilen_segmentler:
                st.error("Videolarda birleştirilecek uygun konuşma/görüntü bölümü bulunamadı.")
                st.stop()
            
            # 4. Kesme, Crossfade Uygulama ve Birleştirme
            durum_metni.text("Seçilen en iyi bölümler geçiş efektleriyle birleştiriliyor (Render)...")
            acik_videolar = {v_yol: VideoFileClip(v_yol) for v_yol, _ in video_yollari}
            final_klipler = []
            
            for i, seg in enumerate(secilen_segmentler):
                bas = max(0, seg["baslangic"] - 0.25)
                bit = min(acik_videolar[seg["video"]].duration, seg["bitis"] + 0.25)
                klip = acik_videolar[seg["video"]].subclipped(bas, bit)
                
                if i > 0 and gecis_suresi > 0:
                    onceki_seg = secilen_segmentler[i - 1]
                    farkli_video = (seg["video"] != onceki_seg["video"])
                    farkli_slayt = (goruntu_benzerligi(seg["kare"], onceki_seg["kare"]) < goruntu_esigi)
                    
                    if (farkli_video or farkli_slayt) and klip.duration > (gecis_suresi * 2):
                        klip = klip.with_effects([
                            vfx.CrossFadeIn(gecis_suresi),
                            afx.AudioFadeIn(gecis_suresi)
                        ])
                        final_klipler[-1] = final_klipler[-1].with_effects([
                            afx.AudioFadeOut(gecis_suresi)
                        ])
                
                final_klipler.append(klip)
            
            cikti_yolu = os.path.join(gecici_dizin, "birlestirilmis_ders.mp4")
            final_video = concatenate_videoclips(final_klipler, method="compose")
            final_video.write_videofile(cikti_yolu, codec="libx264", audio_codec="aac", logger=None)
            
            # Bellek temizliği
            for v in acik_videolar.values():
                v.close()
            
            ilerleme_cubugu.progress(100)
            durum_metni.text("İşlem tamamlandı!")
            
            # Sonuçları Ekranda Göster
            st.success(f"Toplam **{len(tum_segmentler)}** cümle analiz edildi, tekrarlar elenerek **{len(secilen_segmentler)}** eşsiz bölüm birleştirildi.")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("🎥 Oluşturulan Ders Videosu")
                with open(cikti_yolu, "rb") as video_file:
                    video_bytes = video_file.read()
                    st.video(video_bytes)
                    st.download_button(
                        label="⬇️ Videoyu İndir (MP4)",
                        data=video_bytes,
                        file_name="akilli_ders_videosu.mp4",
                        mime="video/mp4",
                        type="primary"
                    )
            
            with col2:
                st.subheader("📋 Kurgu Özeti")
                for idx, seg in enumerate(secilen_segmentler, 1):
                    st.markdown(f"**{idx}. [{seg['dosya_adi']}]** ({seg['baslangic']:.1f}s - {seg['bitis']:.1f}s): *{seg['metin']}*")
