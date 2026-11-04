"""Check HTTPS GitHub releases and install a SHA-256-verified Debian package."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import Request, urlopen


REPOSITORY = "JoaoVictorAAbreu-Dev/attack-shark-r1-ubuntu"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_PACKAGE_BYTES = 50 * 1024 * 1024
USER_AGENT = "attack-shark-r1-ubuntu-updater"


def _get(url, maximum):
    if not url.startswith("https://"):
        raise ValueError("A atualização exige uma conexão HTTPS.")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
    with urlopen(request, timeout=15) as response:
        if not response.geturl().startswith("https://"):
            raise ValueError("O servidor redirecionou a atualização para uma conexão insegura.")
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Arquivo de atualização maior que o limite permitido.")
    return data


def installed_version():
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", "attack-shark-r1"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "0"


def is_newer(current, candidate):
    return subprocess.run(
        ["dpkg", "--compare-versions", current, "lt", candidate],
        check=False,
    ).returncode == 0


def latest_release():
    release = json.loads(_get(RELEASE_API, 1024 * 1024))
    tag = release.get("tag_name", "")
    if not tag.startswith("v"):
        raise ValueError("A versão publicada não tem uma tag válida.")
    version = tag[1:]
    if not version or any(char not in "0123456789." for char in version):
        raise ValueError("A versão publicada não tem um número válido.")
    name = f"attack-shark-r1_{version}_amd64.deb"
    assets = {asset["name"]: asset for asset in release.get("assets", [])}
    if name not in assets or "SHA256SUMS" not in assets:
        raise ValueError("A versão publicada não contém o pacote e seu checksum.")
    if assets[name].get("size", 0) > MAX_PACKAGE_BYTES:
        raise ValueError("Pacote de atualização maior que o limite permitido.")
    return {
        "version": version,
        "package_name": name,
        "package_url": assets[name]["browser_download_url"],
        "checksum_url": assets["SHA256SUMS"]["browser_download_url"],
    }


def _expected_checksum(content, filename):
    for line in content.decode("ascii").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[1].lstrip("*") == filename:
            digest = parts[0].lower()
            if len(digest) == 64 and all(c in "0123456789abcdef" for c in digest):
                return digest
    raise ValueError("Checksum da atualização não encontrado.")


def download_release(release):
    expected = _expected_checksum(_get(release["checksum_url"], 1024 * 1024), release["package_name"])
    data = _get(release["package_url"], MAX_PACKAGE_BYTES)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("O checksum do pacote não confere. Instalação cancelada.")
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "attack-shark-r1"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=cache, prefix=".update-", suffix=".deb", delete=False) as file:
        temporary = Path(file.name)
        file.write(data)
    temporary.chmod(0o600)
    destination = cache / release["package_name"]
    os.replace(temporary, destination)
    return destination


def install_package(path):
    result = subprocess.run(
        ["pkexec", "/usr/bin/dpkg", "-i", str(path)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "A instalação foi cancelada.")
