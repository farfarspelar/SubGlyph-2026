import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from access_control import AccessControl
from dynamic_marking import DynamicMarking
from subglyph import SubGlyphApp, FANUC_ISO


class AccessTests(unittest.TestCase):
    def test_password_persists_without_plaintext(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "permissions.json"
            access = AccessControl(path)
            self.assertTrue(access.check_password("admin"))
            self.assertFalse(access.check_password("wrong"))
            access.set_password("new-password")
            loaded = AccessControl(path)
            self.assertTrue(loaded.check_password("new-password"))
            self.assertFalse(loaded.check_password("admin"))
            self.assertNotIn("new-password", path.read_text())
            with self.assertRaises(ValueError):
                access.set_password("")

    def test_approval_restored_only_for_matching_machine_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "permissions.json"
            access = AccessControl(path)
            config = DynamicMarking(kind="Serienummer")
            config.verify()
            access.approve(config, FANUC_ISO)
            loaded = AccessControl(path)
            restored = DynamicMarking.from_dict(config.to_dict())
            loaded.restore_verification(restored, FANUC_ISO)
            restored.validate(FANUC_ISO)
            changed = DynamicMarking.from_dict(config.to_dict())
            changed.variable = "#522"
            loaded.restore_verification(changed, FANUC_ISO)
            self.assertFalse(changed.verified)
            other = DynamicMarking.from_dict(config.to_dict())
            loaded.restore_verification(other, "OKUMA OSP (ISO)")
            self.assertFalse(other.verified)

    def test_operator_locks_dynamic_text_and_editor_but_admin_can_edit(self):
        app = SimpleNamespace(is_admin=False,
            dynamic_markings=[DynamicMarking(), DynamicMarking(kind="Serienummer"), DynamicMarking(kind="Fast datum")],
            marking_text_entries=[Mock(), Mock(), Mock()], marking_type_buttons=[Mock()])
        SubGlyphApp._update_permissions(app)
        app.marking_text_entries[0].configure.assert_called_with(state="normal")
        for entry in app.marking_text_entries[1:]:
            entry.configure.assert_called_with(state="readonly")
        app.marking_type_buttons[0].configure.assert_called_with(state="disabled")
        SubGlyphApp._edit_dynamic(app, 1)
        app.is_admin = True
        SubGlyphApp._update_permissions(app)
        for entry in app.marking_text_entries:
            entry.configure.assert_called_with(state="normal")
        app.marking_type_buttons[0].configure.assert_called_with(state="normal")
