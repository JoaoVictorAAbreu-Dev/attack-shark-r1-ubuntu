"""Read-only detection of the R1 USB cable and 2.4 GHz receiver."""

from pathlib import Path


USB_DEVICES = Path("/sys/bus/usb/devices")
VENDOR_ID = "1d57"
PRODUCTS = {"fa61": "wired", "fa60": "receiver"}


def scan_usb_modes(root=USB_DEVICES):
    """Return present R1 modes, or None if sysfs cannot be inspected."""
    try:
        devices = list(root.iterdir())
    except OSError:
        return None
    modes = set()
    for device in devices:
        try:
            vendor = (device / "idVendor").read_text(encoding="ascii").strip().lower()
            product = (device / "idProduct").read_text(encoding="ascii").strip().lower()
        except (OSError, UnicodeError):
            continue
        if vendor == VENDOR_ID and product in PRODUCTS:
            modes.add(PRODUCTS[product])
    return frozenset(modes)
