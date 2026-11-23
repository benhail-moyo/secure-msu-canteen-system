"""Issue and verify server-signed meal ticket QR payloads."""
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

LOCAL_TIMEZONE = ZoneInfo("Africa/Harare")


def expiry_for(created_at, extension_days=0):
    placed = created_at.replace(tzinfo=timezone.utc).astimezone(LOCAL_TIMEZONE)
    return datetime.combine(placed.date() + timedelta(days=1 + extension_days), datetime.min.time(), LOCAL_TIMEZONE)


def _b64(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def load_private_key(app):
    configured = app.config.get("TICKET_RSA_PRIVATE_KEY_PEM")
    if configured:
        return serialization.load_pem_private_key(configured.replace("\\n", "\n").encode(), password=None)
    path = Path(app.instance_path) / "ticket_private_key.pem"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        if app.config.get("TICKET_REQUIRE_CONFIGURED_KEY"):
            raise RuntimeError("Configure TICKET_RSA_PRIVATE_KEY_PEM for production")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as file:
                file.write(pem)
        except FileExistsError:
            pass
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def issue_ticket(order, private_key):
    payload = {"v": 1, "id": order.id, "code": order.ticket_code,
               "reg": order.student.student_id,
               "exp": int(expiry_for(order.created_at, order.ticket_extension_days or 0).timestamp())}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = private_key.sign(body, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
    return "MSUT1." + _b64(body) + "." + _b64(signature)


def verify_ticket_payload(value, public_key):
    try:
        prefix, encoded, signature = value.split(".")
        if prefix != "MSUT1":
            return None
        body = _unb64(encoded)
        public_key.verify(_unb64(signature), body, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
        payload = json.loads(body)
        if payload.get("v") != 1 or not isinstance(payload.get("id"), int):
            return None
        return payload
    except (ValueError, TypeError, KeyError, InvalidSignature, UnicodeDecodeError):
        return None
