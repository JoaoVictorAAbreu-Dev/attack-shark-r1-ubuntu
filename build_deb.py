#!/usr/bin/env python3
"""Build the local Attack Shark R1 Ubuntu package from inspected sources."""

from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
PROJECT = Path(os.environ.get("ATTACK_SHARK_OUTPUT_DIR", ROOT / "dist")).resolve()
STAGE = ROOT / "deb-stage"
VERSION = "0.4.0-1"
PACKAGE = PROJECT / "attack-shark-r1_0.4.0_amd64.deb"


def put(source, destination, mode):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(mode)


def write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def main():
    driver = ROOT / "attack-shark-r1"
    if not driver.exists():
        subprocess.run(
            ["cargo", "build", "--release", "--features", "tuning", "--locked"],
            cwd=ROOT / "r1-native", check=True,
        )
        shutil.copyfile(ROOT / "r1-native/target/release/attack-shark-r1", driver)
        driver.chmod(0o755)
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    project_dir = STAGE / "usr/lib/attack-shark-r1"
    put(ROOT / "app_gtk.py", project_dir / "app_gtk.py", 0o644)
    put(ROOT / "updater.py", project_dir / "updater.py", 0o644)
    put(ROOT / "attack-shark-r1", project_dir / "attack-shark-r1", 0o755)
    put(ROOT / "mouse.png", project_dir / "mouse.png", 0o644)
    put(ROOT / "app-icon.png", project_dir / "app-icon.png", 0o644)
    put(ROOT / "launcher.sh", STAGE / "usr/bin/attack-shark-r1-gui", 0o755)
    put(ROOT / "attack-shark-r1.desktop", STAGE / "usr/share/applications/org.local.AttackSharkR1.desktop", 0o644)
    put(ROOT / "app-icon.png", STAGE / "usr/share/pixmaps/attack-shark-r1.png", 0o644)
    put(ROOT / "r1-native/99-attack-shark-r1.rules", STAGE / "usr/lib/udev/rules.d/70-attack-shark-r1.rules", 0o644)
    put(ROOT / "README-ubuntu.md", STAGE / "usr/share/doc/attack-shark-r1/README.md", 0o644)
    put(ROOT / "postinst", STAGE / "DEBIAN/postinst", 0o755)
    put(ROOT / "postrm", STAGE / "DEBIAN/postrm", 0o755)
    write(
        STAGE / "DEBIAN/control",
        f"""Package: attack-shark-r1
Version: {VERSION}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Local package <local@localhost>
Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-4.0, gir1.2-gdkpixbuf-2.0, libudev1, pkexec
Description: Desktop configurator for Attack Shark R1 on Ubuntu
 GTK4 dashboard for DPI, USB polling rate and battery readout.
 Includes an independent Linux driver and device-specific udev permissions.
""",
        0o644,
    )
    write(
        STAGE / "usr/share/doc/attack-shark-r1/copyright",
        """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: attack-shark-r1
Source: https://github.com/jlucaso1/attack-shark-r1
License: MIT or Apache-2.0
Comment: The native driver is based on commit ed6a4c1aa63f31471e26dd5dd7db533905b63ad9.
 The GTK4 dashboard, packaging and --apply-config command were added locally.
 The mouse image and original logo were supplied by the user for this package.
 The application icon was generated from the supplied logo with OpenAI ImageGen.
""",
        0o644,
    )
    for directory in (STAGE, *(path for path in STAGE.rglob("*") if path.is_dir())):
        directory.chmod(0o755)
    PROJECT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["dpkg-deb", "--build", "--root-owner-group", str(STAGE), str(PACKAGE)],
        check=True,
    )
    print(PACKAGE)


if __name__ == "__main__":
    main()
