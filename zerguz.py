#!/usr/bin/env python3

import argparse
import getpass
import hashlib
import os
import struct
import sys

_BACKEND = None

try:
    from Crypto.Cipher import AES as _PycAES
    from Crypto.Random import get_random_bytes as _pycRandomBytes
    _BACKEND = "pycryptodome"
except ImportError:
    pass

if _BACKEND is None:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _CryptoAESGCM
        import secrets as _secrets
        _BACKEND = "cryptography"
    except ImportError:
        pass

if _BACKEND is None:
    print(
        "[HATA] Şifreleme kütüphanesi bulunamadı.\n"
        "Lütfen aşağıdakilerden birini kurun:\n"
        "  pip install pycryptodome\n"
        "  pip install cryptography",
        file=sys.stderr,
    )
    sys.exit(1)


def _random_bytes(n: int) -> bytes:
    if _BACKEND == "pycryptodome":
        return _pycRandomBytes(n)
    return _secrets.token_bytes(n)


def _aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    if _BACKEND == "pycryptodome":
        cipher = _PycAES.new(key, _PycAES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return ciphertext, tag
    else:
        aesgcm = _CryptoAESGCM(key)
        combined = aesgcm.encrypt(nonce, plaintext, None)
        return combined[:-16], combined[-16:]


def _aes_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, tag: bytes) -> bytes:
    if _BACKEND == "pycryptodome":
        cipher = _PycAES.new(key, _PycAES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)
    else:
        aesgcm = _CryptoAESGCM(key)
        try:
            return aesgcm.decrypt(nonce, ciphertext + tag, None)
        except Exception as exc:
            raise ValueError("MAC doğrulama başarısız") from exc


MAGIC = b"ZERGUZ1"
EXTENSION = ".zerguz"
SALT_SIZE = 32
NONCE_SIZE = 16
TAG_SIZE = 16
KEY_SIZE = 32
MAX_ATTEMPTS = 2
PBKDF2_ITERATIONS = 600_000
SHRED_PASSES = 3

HEADER_FIXED_SIZE = len(MAGIC) + SALT_SIZE + NONCE_SIZE + 1


def derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_SIZE,
    )


def secure_delete(filepath: str, passes: int = SHRED_PASSES) -> None:
    try:
        file_size = os.path.getsize(filepath)
        with open(filepath, "r+b") as f:
            fd = f.fileno()
            for _ in range(passes):
                f.seek(0)
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(fd)
            f.seek(0)
            f.write(b"\x00" * file_size)
            f.flush()
            os.fsync(fd)
        os.remove(filepath)
    except OSError as exc:
        print(
            f"[UYARI] Güvenli silme sırasında hata: {exc}\n"
            "Dosya manuel olarak silinmelidir.",
            file=sys.stderr,
        )


def encrypt_file(input_path: str) -> None:
    if not os.path.isfile(input_path):
        print(f"[HATA] Dosya bulunamadı: '{input_path}'", file=sys.stderr)
        sys.exit(1)

    if not os.access(input_path, os.R_OK):
        print(f"[HATA] Okuma izni yok: '{input_path}'", file=sys.stderr)
        sys.exit(1)

    if input_path.endswith(EXTENSION):
        print(
            f"[HATA] Dosya zaten '{EXTENSION}' uzantılı; tekrar şifrelemeye gerek yok.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        password = getpass.getpass("Parola: ")
        if not password:
            print("[HATA] Parola boş olamaz.", file=sys.stderr)
            sys.exit(1)
        password_confirm = getpass.getpass("Parola (tekrar): ")
    except (KeyboardInterrupt, EOFError):
        print("\n[İPTAL] İşlem kullanıcı tarafından iptal edildi.")
        sys.exit(0)

    if password != password_confirm:
        print("[HATA] Parolalar eşleşmiyor. İşlem iptal edildi.", file=sys.stderr)
        sys.exit(1)

    salt = _random_bytes(SALT_SIZE)
    nonce = _random_bytes(NONCE_SIZE)
    key = derive_key(password, salt)

    try:
        with open(input_path, "rb") as f:
            plaintext = f.read()
    except OSError as exc:
        print(f"[HATA] Dosya okunurken hata: {exc}", file=sys.stderr)
        sys.exit(1)

    ciphertext, tag = _aes_gcm_encrypt(key, nonce, plaintext)

    output_path = input_path + EXTENSION

    try:
        with open(output_path, "wb") as f:
            f.write(MAGIC)
            f.write(salt)
            f.write(nonce)
            f.write(struct.pack("B", MAX_ATTEMPTS))
            f.write(ciphertext)
            f.write(tag)
    except OSError as exc:
        print(f"[HATA] Çıktı dosyası yazılırken hata: {exc}", file=sys.stderr)
        sys.exit(1)

    secure_delete(input_path)

    print(
        f"[✓] Şifreleme başarılı.\n"
        f"    Çıktı : {output_path}\n"
        f"    Kaynak: '{input_path}' güvenli biçimde silindi.\n"
        f"    Motor : {_BACKEND}"
    )


def decrypt_file(input_path: str) -> None:
    if not os.path.isfile(input_path):
        print(f"[HATA] Dosya bulunamadı: '{input_path}'", file=sys.stderr)
        sys.exit(1)

    if not input_path.endswith(EXTENSION):
        print(
            f"[HATA] Bu araç yalnızca '{EXTENSION}' uzantılı dosyaları çözer.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.access(input_path, os.R_OK | os.W_OK):
        print(
            f"[HATA] Yeterli dosya izni yok (okuma + yazma gerekli): '{input_path}'",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with open(input_path, "rb") as f:
            raw = f.read()
    except OSError as exc:
        print(f"[HATA] Dosya okunurken hata: {exc}", file=sys.stderr)
        sys.exit(1)

    min_size = HEADER_FIXED_SIZE + TAG_SIZE
    if len(raw) < min_size:
        print("[HATA] Dosya bozuk veya geçersiz formatta.", file=sys.stderr)
        sys.exit(1)

    magic_len = len(MAGIC)
    if raw[:magic_len] != MAGIC:
        print(
            "[HATA] Geçersiz dosya imzası. "
            "Bu dosya ZERGUZ ile şifrelenmemiş ya da bozulmuş olabilir.",
            file=sys.stderr,
        )
        sys.exit(1)

    offset = magic_len
    salt          = raw[offset: offset + SALT_SIZE];                offset += SALT_SIZE
    nonce         = raw[offset: offset + NONCE_SIZE];               offset += NONCE_SIZE
    attempts_left = struct.unpack("B", raw[offset: offset + 1])[0]; offset += 1
    ciphertext    = raw[offset: len(raw) - TAG_SIZE]
    tag           = raw[len(raw) - TAG_SIZE:]

    if attempts_left == 0:
        print(
            "[!] Kalan deneme hakkı yok. Dosya güvenli biçimde imha ediliyor...",
            file=sys.stderr,
        )
        secure_delete(input_path)
        print("[!] Hatalı şifre. Dosya güvenli bir şekilde imha edildi!")
        sys.exit(1)

    try:
        password = getpass.getpass("Parola: ")
    except (KeyboardInterrupt, EOFError):
        print("\n[İPTAL] İşlem kullanıcı tarafından iptal edildi.")
        sys.exit(0)

    key = derive_key(password, salt)

    try:
        plaintext = _aes_gcm_decrypt(key, nonce, ciphertext, tag)

    except (ValueError, KeyError):
        new_attempts = attempts_left - 1

        if new_attempts > 0:
            updated_raw = bytearray(raw)
            attempts_offset = magic_len + SALT_SIZE + NONCE_SIZE
            updated_raw[attempts_offset] = new_attempts
            try:
                with open(input_path, "wb") as f:
                    f.write(bytes(updated_raw))
            except OSError as exc:
                print(f"[UYARI] Sayaç güncellenemedi: {exc}", file=sys.stderr)
            print(
                f"[!] Yanlış şifre! {new_attempts} hakkınız kaldı.",
                file=sys.stderr,
            )
        else:
            print(
                "[!] Son deneme hakkı da kullanıldı. Dosya imha ediliyor...",
                file=sys.stderr,
            )
            secure_delete(input_path)
            print("[!] Hatalı şifre. Dosya güvenli bir şekilde imha edildi!")

        sys.exit(1)

    output_path = input_path[: -len(EXTENSION)]

    if os.path.exists(output_path):
        try:
            choice = input(
                f"[?] '{output_path}' zaten mevcut. Üzerine yazılsın mı? [e/H]: "
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n[İPTAL] İşlem kullanıcı tarafından iptal edildi.")
            sys.exit(0)
        if choice != "e":
            print("[İPTAL] İşlem iptal edildi; mevcut dosya korundu.")
            sys.exit(0)

    try:
        with open(output_path, "wb") as f:
            f.write(plaintext)
    except OSError as exc:
        print(f"[HATA] Çıktı dosyası yazılırken hata: {exc}", file=sys.stderr)
        sys.exit(1)

    secure_delete(input_path)

    print(
        f"[✓] Şifre çözme başarılı.\n"
        f"    Çıktı  : {output_path}\n"
        f"    Şifreli: '{input_path}' güvenli biçimde silindi.\n"
        f"    Motor  : {_BACKEND}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zerguz.py",
        description=(
            "ZERGUZ — AES-256-GCM Dosya Şifreleme/Çözme Aracı\n"
            "GPG benzeri iş akışıyla dosyalarınızı güvenle şifreleyin.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Örnekler:\n"
            "  python3 zerguz.py -e gizli.txt         # gizli.txt → gizli.txt.zerguz\n"
            "  python3 zerguz.py -d gizli.txt.zerguz    # gizli.txt.zerguz → gizli.txt\n\n"
            f"ÖNEMLİ: {MAX_ATTEMPTS} yanlış denemeden sonra şifreli dosya\n"
            "         kalıcı ve kurtarılamaz biçimde imha edilir!"
        ),
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-e", "--encrypt",
        metavar="DOSYA",
        help="Belirtilen dosyayı şifreler; orijinali güvenle siler.",
    )
    group.add_argument(
        "-d", "--decrypt",
        metavar="DOSYA.ozel",
        help="Belirtilen .ozel dosyasını çözer; şifreli kopyayı siler.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.encrypt:
        encrypt_file(args.encrypt)
    elif args.decrypt:
        decrypt_file(args.decrypt)


if __name__ == "__main__":
    main()
