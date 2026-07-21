"""
Teknoloji Haber Bülteni
RSS kaynaklarından haber çeker ve HTML e-posta olarak gönderir.
"""

import html
import logging
import os
import smtplib
import socket
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import feedparser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# RSS istekleri için varsayılan soket zaman aşımı (saniye).
# feedparser kendi timeout parametresini desteklemez; global socket
# timeout'u kullanmak gerekir.
RSS_TIMEOUT_SANIYE = 10

KATEGORI_KAYNAKLARI = {
    "Kurumsal Güvenlik ve Tehdit İstihbaratı": "https://www.bleepingcomputer.com/feed/",
    "Global Teknoloji": "https://shiftdelete.net/feed/",
    "Yapay Zeka": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Kurumsal Uygulamalar": "https://www.itnetwork.com.tr/kategori/kurumsal-uygulamalar/feed",
}

KATEGORI_BASI_HABER = 3


def kategorili_haberleri_cek() -> dict:
    """Her kategori için RSS akışından en güncel haberleri çeker.

    Aynı link'e sahip haberler tekrar eklenmez.
    """
    kategorize_haberler = {}
    eski_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(RSS_TIMEOUT_SANIYE)

    try:
        for kategori_adi, rss_link in KATEGORI_KAYNAKLARI.items():
            haberler = []
            gorulen_linkler = set()

            try:
                feed = feedparser.parse(rss_link)

                if feed.bozo and not feed.entries:
                    raise feed.bozo_exception or ValueError("Akış ayrıştırılamadı")

                for entry in feed.entries:
                    if len(haberler) >= KATEGORI_BASI_HABER:
                        break

                    baslik = getattr(entry, "title", None)
                    link = getattr(entry, "link", None)
                    if not baslik or not link or link in gorulen_linkler:
                        continue

                    gorulen_linkler.add(link)
                    haberler.append({
                        "baslik": baslik.strip(),
                        "link": link.strip(),
                        "yayin_tarihi": getattr(entry, "published", None),
                    })

                logger.info("%s: %d haber çekildi", kategori_adi, len(haberler))

            except Exception as e:
                logger.error("%s kaynağı çekilemedi: %s", kategori_adi, e)

            kategorize_haberler[kategori_adi] = haberler
    finally:
        socket.setdefaulttimeout(eski_timeout)

    return kategorize_haberler


def _haber_bloklari_olustur(kategorize_haberler: dict) -> str:
    bloklar = ""
    for kategori, haberler in kategorize_haberler.items():
        if not haberler:
            continue

        bloklar += f"""
        <tr>
            <td style="padding: 28px 0 10px 0; border-bottom: 1px solid #dcdcdc;">
                <span style="font-size: 13px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: #444444;">
                    {html.escape(kategori)}
                </span>
            </td>
        </tr>
        """

        for haber in haberler:
            baslik = html.escape(haber["baslik"])
            link = html.escape(haber["link"], quote=True)
            bloklar += f"""
            <tr>
                <td style="padding: 14px 0; border-bottom: 1px solid #eeeeee;">
                    <a href="{link}" style="color: #111111; text-decoration: none; font-size: 15px; line-height: 1.5;">
                        {baslik}
                    </a>
                </td>
            </tr>
            """
    return bloklar


def html_bulten_olustur(kategorize_haberler: dict) -> str:
    bugun = datetime.now().strftime("%d.%m.%Y")
    haber_var_mi = any(kategorize_haberler.values())

    icerik = _haber_bloklari_olustur(kategorize_haberler) if haber_var_mi else """
        <tr><td style="padding: 30px 0; color: #666666; font-size: 14px;">
            Bugün için görüntülenecek haber bulunamadı.
        </td></tr>
    """

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 30px 0;">
        <tr>
            <td align="center">
                <table role="presentation" width="620" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border: 1px solid #e0e0e0;">
                    <tr>
                        <td style="padding: 28px 32px 16px 32px; border-bottom: 2px solid #111111;">
                            <span style="font-size: 20px; font-weight: 700; color: #111111;">Teknoloji Bülteni</span>
                            <span style="float: right; font-size: 13px; color: #777777; padding-top: 4px;">{bugun}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 0 32px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                {icerik}
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 24px 32px; color: #999999; font-size: 12px;">
                            Bu bülten otomatik olarak oluşturulmuştur.
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    """


def duz_metin_bulten_olustur(kategorize_haberler: dict) -> str:
    """HTML görüntülenemeyen e-posta istemcileri için düz metin alternatifi."""
    satirlar = [f"Teknoloji Bülteni - {datetime.now().strftime('%d.%m.%Y')}", ""]
    for kategori, haberler in kategorize_haberler.items():
        if not haberler:
            continue
        satirlar.append(kategori.upper())
        for haber in haberler:
            satirlar.append(f"- {haber['baslik']}")
            satirlar.append(f"  {haber['link']}")
        satirlar.append("")
    return "\n".join(satirlar)


def mail_gonder(kategorize_haberler: dict) -> bool:
    gonderen_mail = os.environ.get("GMAIL_USER")
    gonderen_sifre = os.environ.get("GMAIL_PASS")
    alicilar_string = os.environ.get("ALICI_EMAILLER")

    if not gonderen_mail or not gonderen_sifre:
        logger.error("GMAIL_USER / GMAIL_PASS ortam değişkenleri tanımlı değil")
        return False

    if not alicilar_string:
        logger.error("ALICI_EMAILLER ortam değişkeni tanımlı değil")
        return False

    alici_listesi = [a.strip() for a in alicilar_string.split(",") if a.strip()]
    if not alici_listesi:
        logger.error("Geçerli alıcı bulunamadı")
        return False

    if not any(kategorize_haberler.values()):
        logger.warning("Hiçbir kategoride haber bulunamadı; e-posta gönderilmeyecek")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Teknoloji Bülteni - {datetime.now().strftime('%d.%m.%Y')}"
    msg["From"] = gonderen_mail
    msg["To"] = ", ".join(alici_listesi)

    msg.attach(MIMEText(duz_metin_bulten_olustur(kategorize_haberler), "plain", "utf-8"))
    msg.attach(MIMEText(html_bulten_olustur(kategorize_haberler), "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(gonderen_mail, gonderen_sifre)
            server.sendmail(gonderen_mail, alici_listesi, msg.as_string())
        logger.info("Bülten %d alıcıya gönderildi", len(alici_listesi))
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP kimlik doğrulama hatası: kullanıcı adı/şifre (uygulama şifresi) hatalı")
    except (smtplib.SMTPException, OSError) as e:
        logger.error("Mail gönderilirken hata oluştu: %s", e)

    return False


def main() -> None:
    logger.info("Haberler toplanıyor...")
    haber_havuzu = kategorili_haberleri_cek()
    mail_gonder(haber_havuzu)


if __name__ == "__main__":
    main()
