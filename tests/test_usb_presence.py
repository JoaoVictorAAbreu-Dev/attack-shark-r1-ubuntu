"""USB presence checks must not confuse an unplugged mouse with a live R1."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from usb_presence import scan_usb_modes


def device(root, name, vendor, product):
    path = root / name
    path.mkdir()
    (path / "idVendor").write_text(vendor, encoding="ascii")
    (path / "idProduct").write_text(product, encoding="ascii")


class UsbPresenceTests(unittest.TestCase):
    def test_cable_and_receiver_transitions(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(scan_usb_modes(root), frozenset())
            device(root, "mouse", "1d57", "fa61")
            self.assertEqual(scan_usb_modes(root), frozenset({"wired"}))
            device(root, "dongle", "1D57", "FA60")
            self.assertEqual(scan_usb_modes(root), frozenset({"wired", "receiver"}))
            for child in (root / "mouse").iterdir():
                child.unlink()
            (root / "mouse").rmdir()
            self.assertEqual(scan_usb_modes(root), frozenset({"receiver"}))

    def test_other_usb_devices_are_ignored(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            device(root, "unrelated", "1d57", "ffff")
            device(root, "same-product-other-vendor", "ffff", "fa61")
            self.assertEqual(scan_usb_modes(root), frozenset())

    def test_unavailable_sysfs_is_unknown(self):
        with TemporaryDirectory() as directory:
            self.assertIsNone(scan_usb_modes(Path(directory) / "missing"))


if __name__ == "__main__":
    unittest.main()
