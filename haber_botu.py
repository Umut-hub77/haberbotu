"""
Teknoloji Haber Bülteni
RSS kaynaklarından haber çeker ve HTML e-posta olarak gönderir.
"""

import html
import logging
import os
import smtplib
import socket
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# RSS istekleri için varsayılan soket zaman aşımı (saniye).
# feedparser kendi timeout parametresini desteklemez; global socket
# timeout'u kullanmak gerekir.
RSS_TIMEOUT_SANIYE = 15

# Bazı siteler (ör. Cloudflare korumalı) User-Agent göndermeyen istekleri
# engelliyor veya boş/hatalı içerik döndürüyor. Gerçek bir tarayıcı gibi
# görünmek bu tür engellemeleri büyük ölçüde azaltıyor.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Geçici ağ hatalarına (timeout, 403, boş yanıt vb.) karşı her kaynak
# için yapılacak toplam deneme sayısı.
MAX_DENEME = 3
DENEME_ARASI_SANIYE = 3

KATEGORI_KAYNAKLARI = {
    "Kurumsal Güvenlik ve Tehdit İstihbaratı": "https://www.bleepingcomputer.com/feed/",
    "Global Teknoloji": "https://shiftdelete.net/feed/",
    "Yapay Zeka": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Dev Şirketler": "https://venturebeat.com/category/ai/feed/",
}

KATEGORI_BASI_HABER = 3

# Her kategori için vurgu rengi (kart kenarlığı, kaynak noktası, "oku" linki).
KATEGORI_RENKLERI = {
    "Kurumsal Güvenlik ve Tehdit İstihbaratı": "#c0362c",
    "Global Teknoloji": "#1a56db",
    "Yapay Zeka": "#7c3aed",
    "Dev Şirketler": "#0f766e",
}
VARSAYILAN_RENK = "#374151"

TR_AYLAR = {
    1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz",
    7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara",
}


def _kaynak_adi(link: str) -> str:
    """Linkten okunabilir kaynak adı çıkarır (ör. bleepingcomputer.com)."""
    try:
        netloc = urlparse(link).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def _tarih_formatla(ham_tarih: str | None) -> str:
    """RSS 'published' alanını 'gün Ay, SS:DD' formatına çevirir."""
    if not ham_tarih:
        return ""
    try:
        dt = parsedate_to_datetime(ham_tarih)
        return f"{dt.day} {TR_AYLAR[dt.month]}, {dt.strftime('%H:%M')}"
    except Exception:
        return ""


def _kaynagi_dene(kategori_adi: str, rss_link: str) -> list:
    """Tek bir RSS kaynağını, geçici hatalara karşı birkaç kez deneyerek çeker.

    Boş/hatalı yanıt (403, timeout, engelleme vb.) alınırsa kısa bir
    bekleme sonrası tekrar dener; tüm denemeler başarısız olursa boş
    liste döner ve hata loglanır.
    """
    son_hata = None

    for deneme in range(1, MAX_DENEME + 1):
        try:
            feed = feedparser.parse(rss_link, agent=USER_AGENT)

            http_durumu = getattr(feed, "status", None)
            if http_durumu is not None and http_durumu >= 400:
                raise ConnectionError(f"HTTP {http_durumu} yanıtı alındı")

            if feed.bozo and not feed.entries:
                raise feed.bozo_exception or ValueError("Akış ayrıştırılamadı")

            if not feed.entries:
                raise ValueError("Akışta hiç haber bulunamadı (boş yanıt)")

            haberler = []
            gorulen_linkler = set()

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

            return haberler

        except Exception as e:
            son_hata = e
            if deneme < MAX_DENEME:
                logger.warning(
                    "%s: %d. deneme başarısız (%s), tekrar denenecek...",
                    kategori_adi, deneme, e,
                )
                time.sleep(DENEME_ARASI_SANIYE)

    logger.error("%s kaynağı %d denemede de çekilemedi: %s", kategori_adi, MAX_DENEME, son_hata)
    return []


def kategorili_haberleri_cek() -> dict:
    """Her kategori için RSS akışından en güncel haberleri çeker.

    Aynı link'e sahip haberler tekrar eklenmez. Geçici ağ hatalarına karşı
    her kaynak birkaç kez denenir.
    """
    kategorize_haberler = {}
    eski_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(RSS_TIMEOUT_SANIYE)

    try:
        for kategori_adi, rss_link in KATEGORI_KAYNAKLARI.items():
            haberler = _kaynagi_dene(kategori_adi, rss_link)
            logger.info("%s: %d haber çekildi", kategori_adi, len(haberler))
            kategorize_haberler[kategori_adi] = haberler
    finally:
        socket.setdefaulttimeout(eski_timeout)

    return kategorize_haberler


def _haber_bloklari_olustur(kategorize_haberler: dict) -> str:
    bloklar = ""
    for kategori, haberler in kategorize_haberler.items():
        if not haberler:
            continue

        renk = KATEGORI_RENKLERI.get(kategori, VARSAYILAN_RENK)

        bloklar += f"""
        <tr>
            <td style="padding: 30px 0 4px 0;">
                <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                        <td width="4" style="background-color: {renk}; border-radius: 2px;">&nbsp;</td>
                        <td style="padding-left: 10px;">
                            <span style="font-size: 14px; font-weight: 700; color: #111827;">
                                {html.escape(kategori)}
                            </span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        """

        for haber in haberler:
            baslik = html.escape(haber["baslik"])
            link = html.escape(haber["link"], quote=True)
            kaynak = html.escape(_kaynak_adi(haber["link"]))
            tarih = html.escape(_tarih_formatla(haber.get("yayin_tarihi")))
            meta = "  ·  ".join(p for p in (kaynak, tarih) if p)

            bloklar += f"""
            <tr>
                <td style="padding: 6px 0;">
                    <table role="presentation" cellpadding="0" cellspacing="0" width="100%"
                           style="background-color: #ffffff; border: 1px solid #e8eaee; border-radius: 8px;">
                        <tr>
                            <td style="padding: 16px 18px;">
                                <a href="{link}" style="color: #111827; text-decoration: none; font-size: 15px; font-weight: 600; line-height: 1.45; display: block;">
                                    {baslik}
                                </a>
                                <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin-top: 10px;">
                                    <tr>
                                        <td style="font-size: 12px; color: #9ca3af;">
                                            {meta}
                                        </td>
                                        <td align="right">
                                            <a href="{link}" style="font-size: 12px; font-weight: 600; color: {renk}; text-decoration: none; white-space: nowrap;">
                                                Devamını oku &rarr;
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            """
    return bloklar


def html_bulten_olustur(kategorize_haberler: dict) -> str:
    bugun = datetime.now().strftime("%d %B %Y").replace(
        datetime.now().strftime("%B"),
        {
            "January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan",
            "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos",
            "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık",
        }[datetime.now().strftime("%B")]
    )
    toplam_haber = sum(len(v) for v in kategorize_haberler.values())
    haber_var_mi = toplam_haber > 0

    icerik = _haber_bloklari_olustur(kategorize_haberler) if haber_var_mi else """
        <tr><td style="padding: 40px 0; color: #6b7280; font-size: 14px; text-align:center;">
            Bugün için görüntülenecek haber bulunamadı.
        </td></tr>
    """

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #eef0f3; padding: 32px 0;">
        <tr>
            <td align="center">
                <table role="presentation" width="640" cellpadding="0" cellspacing="0"
                       style="background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb;">
                    <tr>
                        <td style="background-color: #0b1220; padding: 30px 32px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td>
                                        <span style="font-size: 21px; font-weight: 700; color: #ffffff; letter-spacing: 0.2px;">IT Gündem</span>
                                        <div style="font-size: 12.5px; color: #9aa4b2; margin-top: 4px;">
                                            Günlük teknoloji ve güvenlik özeti &mdash; {toplam_haber} başlık
                                        </div>
                                    </td>
                                    <td align="right" style="vertical-align: top;">
                                        <span style="font-size: 12.5px; color: #c7ccd4; background-color: rgba(255,255,255,0.08); padding: 6px 12px; border-radius: 20px;">
                                            {bugun}
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 18px 32px 24px 32px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                {icerik}
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 18px 32px; border-top: 1px solid #eef0f3; color: #9ca3af; font-size: 11.5px;">
                            Bu bülten otomatik olarak oluşturulmuştur &middot; Kaynak sayısı: {len(kategorize_haberler)}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    """


def duz_metin_bulten_olustur(kategorize_haberler: dict) -> str:
    """HTML görüntülenemeyen e-posta istemcileri için düz metin alternatifi."""
    satirlar = [f"IT Gündem - {datetime.now().strftime('%d.%m.%Y')}", ""]
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
    msg["Subject"] = f"IT Gündem - {datetime.now().strftime('%d.%m.%Y')}"
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
