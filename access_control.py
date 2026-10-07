"""Local administrator credentials and machine-approved marking settings."""
import hashlib
import hmac
import json
import secrets


class AccessControl:
    def __init__(self, path):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.data = {"approved": []}
            self.set_password("admin")

    def _save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.path)

    def set_password(self, password):
        if not password:
            raise ValueError("Lösenordet får inte vara tomt.")
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200000)
        previous = dict(self.data)
        self.data.update(salt=salt, password_hash=digest.hex())
        try:
            self._save()
        except OSError:
            self.data = previous
            raise

    def check_password(self, password):
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(self.data["salt"]), 200000)
        return hmac.compare_digest(digest.hex(), self.data["password_hash"])

    @staticmethod
    def fingerprint(config, controller):
        payload = json.dumps([controller, config.to_dict()], sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def approve(self, config, controller):
        key = self.fingerprint(config, controller)
        if key not in self.data["approved"]:
            self.data["approved"].append(key)
            self._save()

    def restore_verification(self, config, controller):
        if self.fingerprint(config, controller) in self.data["approved"]:
            config.verify()
