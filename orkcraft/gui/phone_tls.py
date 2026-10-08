"""The phone listener's certificate (docs/design/mobile.md §2 TLS): self-signed, made on its first start
and kept beside the machine's settings (`phone.crt`, `phone.key`, both 0600). A phone pins its SHA-256
fingerprint, which the pairing QR code carries, instead of trusting a CA; so the certificate's names and
dates are not what makes it trusted, and it lives long (a new one would unpair every phone).

    cert, key = ensure()            # the files, made once
    fingerprint(cert)               # "AB:CD:…": SHA-256 of the certificate's DER bytes
    context(cert, key)              # the server's ssl.SSLContext (TLS 1.2 at least)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import ssl
from pathlib import Path

from orkcraft import settings

YEARS = 20


class TlsError(Exception):
    """The certificate cannot be made or read here; its text is shown to the person."""


def paths(folder: Path | None = None) -> tuple[Path, Path]:
    folder = folder or settings.path().parent
    return folder / "phone.crt", folder / "phone.key"


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def ensure(folder: Path | None = None) -> tuple[Path, Path]:
    """The certificate and its key, made on the first call (an EC P-256 key, self-signed)."""
    cert, key = paths(folder)
    if cert.is_file() and key.is_file():
        return cert, key
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
    except ImportError:
        raise TlsError("Pairing a phone needs the cryptography package: pip install 'orkcraft[gui]'") from None
    private = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Orkcraft town")])
    now = dt.datetime.now(dt.timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                   .public_key(private.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=365 * YEARS))
                   .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                   .sign(private, hashes.SHA256()))
    _write_private(key, private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
    _write_private(cert, certificate.public_bytes(serialization.Encoding.PEM))
    return cert, key


def fingerprint(cert: Path) -> str:
    """The SHA-256 of the certificate's DER bytes, as pairs of hex digits joined by colons."""
    der = ssl.PEM_cert_to_DER_cert(cert.read_text(encoding="ascii"))
    return ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())


def context(cert: Path, key: Path) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert, key)
    return ctx
