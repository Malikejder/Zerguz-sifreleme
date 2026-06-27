<div align="center">

# ⚡ ZERGUZ
**2 yanlış parola denemesinde dosya kendi kendini kalıcı olarak imha eder.**

</div>

---

## 📋 İçindekiler

- [Özellikler](#-özellikler)
- [Nasıl Çalışır](#-nasıl-çalışır)
- [Kurulum](#-kurulum)
- [Kullanım](#-kullanım)
- [Dosya Formatı](#-dosya-formatı)
- [Güvenlik Mimarisi](#-güvenlik-mimarisi)
- [İmha Mekanizması](#-imha-mekanizması)
- [Hata Mesajları](#-hata-mesajları)
- [Sınırlılıklar ve Uyarılar](#️-sınırlılıklar-ve-uyarılar)
- [Lisans](#-lisans)

---

## ✨ Özellikler

| Özellik | Detay |
|---|---|
| 🔒 Şifreleme Algoritması | AES-256-GCM (kimlik doğrulamalı şifreleme) |
| 🔑 Anahtar Türetme | PBKDF2-HMAC-SHA256 · 600 000 iterasyon (OWASP 2023) |
| 🧂 Tuzlama | Her dosya için 32 bayt kriptografik rastgele Salt |
| 💣 Kendi Kendini İmha | 2 yanlış denemede `shred` mantığıyla kalıcı silme |
| 🔄 Çift Kütüphane Desteği | `pycryptodome` **veya** `cryptography` (otomatik algılama) |
| 🗑️ Güvenli Silme | 3 tur `os.urandom` + 1 tur sıfır + `fsync` |
| 📦 Tek Dosya | Sıfır bağımlılık dışı; yalnızca bir Python dosyası |
| 🐍 Kod Kalitesi | PEP 8, type hints, tam `try/except` hata yönetimi |

---

## 🔍 Nasıl Çalışır

```
┌─────────────────────────────────────────────────────────────────┐
│                        ŞİFRELEME AKIŞI                          │
└─────────────────────────────────────────────────────────────────┘

  dosya.txt  ──►  [Parola × 2]  ──►  PBKDF2(parola, salt)
                                           │
                                      AES-256-GCM
                                           │
                                    dosya.txt.ozel
                                           │
                              Orijinal → secure_delete()


┌─────────────────────────────────────────────────────────────────┐
│                       ŞİFRE ÇÖZME AKIŞI                         │
└─────────────────────────────────────────────────────────────────┘

  dosya.txt.ozel  ──►  [Parola]  ──►  Doğru mu?
                                           │
                          ┌────────────────┴────────────────┐
                        EVET                               HAYIR
                          │                                  │
                    dosya.txt                      attempts_left - 1
                    (geri gelir)                        │
                          │                    ┌──────────┴──────────┐
                 .ozel → secure_delete()     > 0                   == 0
                                               │                     │
                                          "X hakkınız           secure_delete()
                                           kaldı" uyarısı       "İmha edildi!"
```

---

## 🚀 Kurulum

### Gereksinimler

- Python 3.10 veya üzeri
- `pycryptodome` **ya da** `cryptography` kütüphanesi (ikisinden biri yeterli)

### 1. Depoyu Klonla

```bash
git clone https://github.com/Malikejder/zerguz.git
cd zerguz
```

### 2. Kütüphaneyi Kur

```bash
# Tercih edilen — pycryptodome
pip install pycryptodome

# Alternatif — cryptography
pip install cryptography
```

> **Not:** Program başlatıldığında `pycryptodome`'u önce arar; bulamazsa `cryptography`'ye otomatik olarak geçer. İkisi de kuruluysa `pycryptodome` öncelik alır.

---

## 💻 Kullanım

### Şifreleme

```bash
python3 main.py -e <dosya>
```

Örnek:

```
$ python3 main.py -e rapor.pdf
Parola:
Parola (tekrar):

[✓] Şifreleme başarılı.
    Çıktı : rapor.pdf.ozel
    Kaynak: 'rapor.pdf' güvenli biçimde silindi.
    Motor : pycryptodome
```

- Parola **iki kez** istenir (doğrulama)
- Orijinal dosya şifreleme sonunda **güvenli biçimde silinir**
- Çıktı: `<dosyaadı>.ozel`

---

### Şifre Çözme

```bash
python3 main.py -d <dosya.ozel>
```

Örnek:

```
$ python3 main.py -d rapor.pdf.ozel
Parola:

[✓] Şifre çözme başarılı.
    Çıktı  : rapor.pdf
    Şifreli: 'rapor.pdf.ozel' güvenli biçimde silindi.
    Motor  : pycryptodome
```

- Doğru parola girilirse orijinal dosya geri gelir
- Şifreli `.ozel` dosyası **güvenli biçimde silinir**

---

### Yardım

```bash
python3 main.py --help
```

```
usage: main.py [-h] (-e DOSYA | -d DOSYA.ozel)

ZERGUZ — AES-256-GCM Dosya Şifreleme/Çözme Aracı

options:
  -h, --help            show this help message and exit
  -e, --encrypt DOSYA   Belirtilen dosyayı şifreler; orijinali güvenle siler.
  -d, --decrypt DOSYA.ozel
                        Belirtilen .ozel dosyasını çözer; şifreli kopyayı siler.

ÖNEMLİ: 2 yanlış denemeden sonra şifreli dosya
         kalıcı ve kurtarılamaz biçimde imha edilir!
```

---

## 📦 Dosya Formatı

Şifrelenmiş `.ozel` dosyaları aşağıdaki binary yapıya sahiptir:

```
Offset   Boyut    Alan             Açıklama
───────────────────────────────────────────────────────────
0        7 B      MAGIC            "ZERGUZ1" — dosya imzası
7        32 B     SALT             PBKDF2 tuzlama değeri (her şifrelemede farklı)
39       16 B     NONCE            AES-GCM başlatma vektörü
55       1 B      ATTEMPTS_LEFT    Kalan parola denemesi (başlangıç: 2)
56       N B      CIPHERTEXT       AES-256-GCM ile şifrelenmiş veri
56+N     16 B     TAG              GCM kimlik doğrulama etiketi
```

> **ATTEMPTS_LEFT** alanı yanlış her denemede doğrudan dosyada güncellenir; dosya yeniden oluşturulmaz, yalnızca bu tek bayt yazılır.

---

## 🛡️ Güvenlik Mimarisi

### Şifreleme: AES-256-GCM

AES-256-GCM, **AEAD** (Authenticated Encryption with Associated Data) kategorisinde yer alır. Tek geçişte hem **gizlilik** hem de **bütünlük** sağlar.

- Gizlilik: Kimse içeriği okuyamaz
- Bütünlük: Dosya değiştirildiyse `TAG` doğrulaması başarısız olur ve şifre çözme reddedilir
- Kaba kuvvet saldırısına karşı 2²⁵⁶ ≈ 1.16 × 10⁷⁷ olası anahtar

### Anahtar Türetme: PBKDF2-HMAC-SHA256

Kullanıcı parolası doğrudan anahtar olarak kullanılmaz; PBKDF2 ile türetilir:

```
AES_Anahtarı = PBKDF2(
    hash      = SHA-256,
    password  = kullanıcı_parolası,
    salt      = rastgele_32_bayt,
    iteration = 600_000,       # OWASP 2023 minimum önerisi
    dklen     = 32             # 256 bit → AES-256
)
```

600 000 iterasyon, modern donanımda kaba kuvvet saldırısını milyonlarca kat yavaşlatır.

### Güvenli Silme: Shred Mantığı

```
Tur 1  →  os.urandom(dosya_boyutu)  +  fsync   # Rastgele baytlar
Tur 2  →  os.urandom(dosya_boyutu)  +  fsync   # Rastgele baytlar
Tur 3  →  os.urandom(dosya_boyutu)  +  fsync   # Rastgele baytlar
Son    →  b"\x00" × dosya_boyutu    +  fsync   # Sıfırlar
           os.remove()                          # Dosya adı kaldırılır
```

---

## 💣 İmha Mekanizması

```
İlk açılışta    →  ATTEMPTS_LEFT = 2

1. yanlış giriş →  ATTEMPTS_LEFT = 1
                   "[!] Yanlış şifre! 1 hakkınız kaldı."

2. yanlış giriş →  secure_delete() tetiklenir
                   3 tur urandom + sıfır + os.remove()
                   "[!] Hatalı şifre. Dosya güvenli bir şekilde imha edildi!"
```

> ⚠️ **Bu işlem geri alınamaz.** Dosya imha edildikten sonra hiçbir kurtarma aracı içeriğe erişemez.

---

## ⚠️ Hata Mesajları

| Mesaj | Anlam |
|---|---|
| `[HATA] Dosya bulunamadı` | Belirtilen dosya mevcut değil |
| `[HATA] Okuma izni yok` | Dosya sistemi izin hatası |
| `[HATA] Parolalar eşleşmiyor` | Şifreleme sırasında iki parola farklı girildi |
| `[HATA] Geçersiz dosya imzası` | Dosya ZERGUZ ile şifrelenmemiş ya da bozulmuş |
| `[!] Yanlış şifre! X hakkınız kaldı` | Parola yanlış; X deneme hakkı kaldı |
| `[!] Dosya güvenli bir şekilde imha edildi!` | Tüm haklar tükendi; dosya yok edildi |
| `[UYARI] Güvenli silme sırasında hata` | `shred` kısmen başarısız; manuel silme gerekebilir |

---

## ⚙️ Sınırlılıklar ve Uyarılar

**SSD / Flash Depolama**
`shred` mantığı HDD üzerinde çok daha etkilidir. SSD'lerde wear-leveling ve TRIM özellikleri nedeniyle üzerine yazma her zaman fiziksel olarak aynı bloğa gitmeyebilir. Gerçek güvenlik için tam disk şifreleme (LUKS, BitLocker) ile birlikte kullanılması önerilir.

**Parola Güvenliği**
Zayıf bir parola seçmek, tüm kriptografik güvenceyi anlamsız kılar. En az 12 karakter, büyük/küçük harf + rakam + sembol içeren parolalar kullanın.

**Yedek Yok**
Şifreli dosya imha edildikten sonra içerik **kurtarılamaz**. Kritik veriler için `.ozel` dosyasını imha öncesinde farklı bir konuma yedeklemeniz önerilir.

**Platform**
Öncelikli olarak Linux/macOS üzerinde geliştirilip test edilmiştir. Windows'ta `os.fsync()` davranışı farklılık gösterebilir.

---

## 📁 Proje Yapısı

```
zerguz/
├── main.py        # Tek dosya; tüm program burada
└── README.md      # Bu dosya
```

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.

---

<div align="center">

**ZERGUZ** · AES-256-GCM · PBKDF2-SHA256 · Kendi Kendini İmha

*Parolanızı unutmayın. Hiçbir kurtarma seçeneği yoktur.*

</div>
