import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def mail_gonder(haber_listesi, alici_listesi):
    # Kendi e-posta bilgilerin (Gmail kullanıyorsan "App Passwords" oluşturman gerekir)
    GONDEREN_MAIL = "seninmailin@gmail.com"
    GONDEREN_SIFRE = "uygulama_sifresi_buraya"
    
    # 1. HTML İçeriğini Dinamik Oluşturma
    html_icerik = """
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f9f9f9; padding: 20px; border-radius: 8px;">
        <h2 style="color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px;">Günlük Teknoloji Özeti</h2>
    """
    
    # Haberleri tek tek HTML şablonuna ekliyoruz (Sadece başlık ve link)
    for haber in haber_listesi:
        html_icerik += f"""
        <div style="padding: 15px 0; border-bottom: 1px solid #e0e0e0;">
            <h3 style="margin: 0 0 8px 0; color: #1a1a1a; font-size: 18px;">{haber['baslik']}</h3>
            <a href="{haber['link']}" style="color: #007bff; text-decoration: none; font-weight: bold; font-size: 14px;">Haberi Oku &rarr;</a>
        </div>
        """
    
    html_icerik += "</div>"

    # 2. E-posta Paketini Hazırlama
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Günün Öne Çıkan Teknoloji Haberleri"
    msg['From'] = GONDEREN_MAIL
    
    # MIMEText ile HTML formatını tanımlıyoruz
    part = MIMEText(html_icerik, 'html')
    msg.attach(part)

    # 3. SMTP Sunucusuna Bağlanıp Gönderme
    try:
        # Gmail için SMTP ayarları (Port 587)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # Güvenli bağlantı başlat
        server.login(GONDEREN_MAIL, GONDEREN_SIFRE)
        
        # BCC mantığı ile herkese gönder (Herkes e-postayı sadece kendine gelmiş gibi görür)
        server.sendmail(GONDEREN_MAIL, alici_listesi, msg.as_string())
        server.quit()
        print("E-postalar başarıyla gönderildi!")
        
    except Exception as e:
        print(f"Hata oluştu: {e}")

# Sistemi Test Etme
ornek_haberler = [
    {"baslik": "Apple, yeni işletim sistemi güncellemelerini duyurdu", "link": "https://ornek.com/haber1"},
    {"baslik": "NVIDIA, yapay zeka odaklı yeni çiplerini tanıttı", "link": "https://ornek.com/haber2"},
    {"baslik": "Avrupa Birliği'nden teknoloji devlerine yeni regülasyon", "link": "https://ornek.com/haber3"}
]

# Hedef 3 kişi
alici_listesi = ["kisi1@email.com", "kisi2@email.com", "kisi3@email.com"]

mail_gonder(ornek_haberler, alici_listesi)
