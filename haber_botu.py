import feedparser
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def gercek_haberleri_cek():
    # Dünyanın en büyük teknoloji ve iş dünyası haber kaynakları (RSS Feed'ler)
    rss_kaynaklari = [
        "https://techcrunch.com/feed/",                                        # Big Tech ve Girişimler
        "https://www.theverge.com/rss/index.xml",                              # Teknoloji Devleri ve Tüketici
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910" # CNBC Tech (İş dünyası odaklı)
    ]
    
    cekilen_haberler = []
    kaynak_basi_haber_sayisi = 5 # 3 kaynaktan 5'er haber = Toplam 15 haber
    
    for kaynak in rss_kaynaklari:
        try:
            feed = feedparser.parse(kaynak)
            sayac = 0
            for entry in feed.entries:
                if sayac >= kaynak_basi_haber_sayisi:
                    break
                
                cekilen_haberler.append({
                    "baslik": entry.title,
                    "link": entry.link
                })
                sayac += 1
        except Exception as e:
            print(f"Haber çekilirken hata oluştu ({kaynak}): {e}")
            
    return cekilen_haberler

def mail_gonder(haber_listesi):
    GONDEREN_MAIL = os.environ.get("GMAIL_USER")
    GONDEREN_SIFRE = os.environ.get("GMAIL_PASS")
    ALICILAR_STRING = os.environ.get("ALICI_MAILLER")
    
    if not ALICILAR_STRING:
        print("Alıcı e-posta listesi bulunamadı!")
        return

    alici_listesi = ALICILAR_STRING.split(",")
    
    # 1. HTML İçeriğini Dinamik Oluşturma
    html_icerik = """
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
        <h2 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 15px; margin-top: 0;">Dünya Teknoloji Gündemi</h2>
    """
    
    for haber in haber_listesi:
        html_icerik += f"""
        <div style="padding: 20px 0; border-bottom: 1px solid #f0f0f0;">
            <h3 style="margin: 0 0 12px 0; color: #1a1a1a; font-size: 17px; line-height: 1.4;">{haber['baslik']}</h3>
            <a href="{haber['link']}" style="display: inline-block; color: #ffffff; background-color: #3498db; text-decoration: none; font-weight: 600; font-size: 13px; padding: 8px 16px; border-radius: 6px;">Haberi Oku</a>
        </div>
        """
    
    html_icerik += "</div>"

    # 2. E-posta Paketini Hazırlama
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "🌍 Küresel Teknoloji Gündemi: Öne Çıkan Gelişmeler"
    msg['From'] = GONDEREN_MAIL
    
    part = MIMEText(html_icerik, 'html')
    msg.attach(part)

    # 3. SMTP Sunucusuna Bağlanıp Gönderme
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GONDEREN_MAIL, GONDEREN_SIFRE)
        server.sendmail(GONDEREN_MAIL, alici_listesi, msg.as_string())
        server.quit()
        print(f"{len(haber_listesi)} adet küresel haber başarıyla gönderildi!")
        
    except Exception as e:
        print(f"Mail gönderilirken hata oluştu: {e}")

# Sistemin ana çalışma akışı
if __name__ == "__main__":
    print("Dünya çapında haberler toplanıyor...")
    bugunun_haberleri = gercek_haberleri_cek()
    
    if len(bugunun_haberleri) > 0:
        print(f"Toplam {len(bugunun_haberleri)} haber bulundu. Mailler hazırlanıyor...")
        mail_gonder(bugunun_haberleri)
    else:
        print("Haber çekilemediği için mail gönderilmedi.")
