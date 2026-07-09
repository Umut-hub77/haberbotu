import feedparser
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def kategorili_haberleri_cek():
    # İngilizce ve Türkçe kaynakların karmaşık (mixed) listesi
    kategori_kaynaklari = {
    "Kurumsal Güvenlik ve Tehdit İstihbaratı": "https://www.bleepingcomputer.com/feed/",
    "Global Teknoloji": "https://shiftdelete.net/feed",
    "Yapay Zeka:" "https://techcrunch.com/category/artificial-intelligence/feed/"
    }
    
    kategorize_haberler = {}
    kategori_basi_haber = 4
    
    for kategori_adi, rss_link in kategori_kaynaklari.items():
        kategorize_haberler[kategori_adi] = []
        try:
            feed = feedparser.parse(rss_link)
            sayac = 0
            for entry in feed.entries:
                if sayac >= kategori_basi_haber:
                    break
                
                kategorize_haberler[kategori_adi].append({
                    "baslik": entry.title,
                    "link": entry.link
                })
                sayac += 1
        except Exception as e:
            print(f"Hata ({kategori_adi} çekilemedi): {e}")
            
    return kategorize_haberler

def mail_gonder(kategorize_haberler):
    GONDEREN_MAIL = os.environ.get("GMAIL_USER")
    GONDEREN_SIFRE = os.environ.get("GMAIL_PASS")
    ALICILAR_STRING = os.environ.get("ALICI_EMAILLER")
    
    if not ALICILAR_STRING:
        print("Alıcı listesi bulunamadı!")
        return

    alici_listesi = ALICILAR_STRING.split(",")
    
    html_icerik = """
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 650px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #2c3e50; margin: 0; font-size: 28px;">TechPulse</h1>
            <p style="color: #7f8c8d; margin-top: 5px; font-size: 14px;">Günlük Teknoloji Özeti (EN & TR)</p>
        </div>
    """
    
    for kategori, haberler in kategorize_haberler.items():
        if len(haberler) > 0:
            html_icerik += f"""
            <div style="background-color: #f8f9fa; padding: 10px 15px; border-left: 4px solid #3498db; margin: 25px 0 15px 0;">
                <h2 style="margin: 0; color: #2c3e50; font-size: 18px;">{kategori}</h2>
            </div>
            """
            for haber in haberler:
                html_icerik += f"""
                <div style="padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
                    <h3 style="margin: 0 0 10px 0; color: #1a1a1a; font-size: 16px; line-height: 1.4;">{haber['baslik']}</h3>
                    <a href="{haber['link']}" style="display: inline-block; color: #ffffff; background-color: #3498db; text-decoration: none; font-weight: 600; font-size: 12px; padding: 6px 14px; border-radius: 4px;">Haberi Oku</a>
                </div>
                """
    
    html_icerik += "</div>"

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Küresel Teknoloji Gündemi: Öne Çıkan Gelişmeler"
    msg['From'] = GONDEREN_MAIL
    
    part = MIMEText(html_icerik, 'html')
    msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GONDEREN_MAIL, GONDEREN_SIFRE)
        server.sendmail(GONDEREN_MAIL, alici_listesi, msg.as_string())
        server.quit()
        print("İngilizce-Türkçe karışık bülten başarıyla gönderildi!")
        
    except Exception as e:
        print(f"Mail gönderilirken hata oluştu: {e}")

if __name__ == "__main__":
    print("Karma dilde haberler toplanıyor...")
    haber_havuzu = kategorili_haberleri_cek()
    mail_gonder(haber_havuzu)
