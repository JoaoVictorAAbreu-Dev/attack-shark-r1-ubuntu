#!/usr/bin/python3
"""Attack Shark R1 dashboard for Ubuntu (GTK 4)."""

import os
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
from updater import download_release, install_package, installed_version, is_newer, latest_release


APP_ID = "org.local.AttackSharkR1"
ASSET_DIR = Path(__file__).resolve().parent
DRIVER = ASSET_DIR / "attack-shark-r1"
MOUSE_IMAGE = ASSET_DIR / "mouse.png"
APP_ICON = ASSET_DIR / "app-icon.png"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
CONFIG = CONFIG_DIR / "attack-shark-r1.ini"
DEFAULTS = {
    "polling_rate": "1000",
    "sleep_time": "6.0",
    "deep_sleep_time": "12",
    "key_response_time": "4",
    "dpis": "800 1600 3200 4000 5000 12000",
    "active_dpi": "3",
    "ripple_control": "false",
    "angle_snap": "false",
}

CSS = """
@define-color canvas #f4f7fc;
@define-color ink #142039;
@define-color muted #61708a;
@define-color accent #245bd7;
@define-color accent_hover #174dbd;
@define-color field_border #dbe4f2;
window { background: @canvas; color: @ink; font-family: Cantarell, sans-serif; }
.page { background: linear-gradient(135deg, #f9fbff, #ecf2fb 65%, #f8fbff); }
.brand { color: @muted; font-size: 11px; font-weight: 800; letter-spacing: 2px; }
.heading { color: #15223a; font-size: 28px; font-weight: 800; }
.subheading { color: @muted; font-size: 13px; }
.glass { background: rgba(255, 255, 255, 0.86); border: 1px solid #ffffff;
         border-radius: 24px; box-shadow: 0 12px 36px rgba(64, 86, 129, 0.10); }
.hero { background: linear-gradient(155deg, rgba(255,255,255,0.98), rgba(228,237,252,0.80));
        border: 1px solid #ffffff; border-radius: 28px;
        box-shadow: 0 16px 45px rgba(61, 84, 124, 0.13); }
.section-title { color: #1c2b47; font-size: 18px; font-weight: 800; }
.section-note { color: #68758c; font-size: 12px; }
.field-label { color: #3f4f69; font-size: 13px; font-weight: 600; }
.eyebrow { color: #5871a8; font-size: 11px; font-weight: 800; letter-spacing: 1.4px; }
.battery { color: #172b4c; font-size: 42px; font-weight: 800; }
.status { color: #52627d; font-size: 12px; }
.badge { background: #e8f0ff; color: #2457a6; border-radius: 999px;
         padding: 8px 14px; font-size: 12px; font-weight: 700; }
.badge-error { background: #fff0ed; color: #9d352e; }
.profile-row { background: #f7f9fd; border: 1px solid #e8eef8; border-radius: 14px; padding: 7px 10px; }
.profile-active { background: #eaf2ff; border-color: #91b8f2; }
.number { color: #4972ae; font-size: 12px; font-weight: 800; }
spinbutton, dropdown { background: #ffffff; color: #172b4c; border: 1px solid @field_border;
                       border-radius: 10px; min-height: 34px; }
spinbutton:focus-within, dropdown:focus { border-color: #2563eb; }
.rate { background: #f2f5fb; color: #465771; border: 1px solid #e1e9f5;
        border-radius: 10px; min-height: 40px; font-weight: 700; }
.rate:checked { background: #dbe9ff; color: #174a9a; border-color: #9bc0f8; }
.rate:focus, button:focus { outline: 2px solid #2563eb; outline-offset: 2px; }
.primary { background: @accent; color: #ffffff; border-radius: 13px;
           min-height: 46px; padding: 0 20px; font-weight: 800; }
.primary:hover { background: @accent_hover; }
.primary:disabled { background: #9aaccb; }
.secondary { background: #eef4ff; color: #2155ad; border-radius: 11px;
             min-height: 38px; padding: 0 12px; font-weight: 700; }
.secondary:hover { background: #dfeaff; }
.feedback { background: #eaf2ff; color: #174a87; border-radius: 12px; padding: 10px 14px; }
.feedback-error { background: #fff0ed; color: #90322e; }
"""


def css(widget, *names):
    for name in names:
        widget.add_css_class(name)
    return widget


def label(text, *classes):
    widget = Gtk.Label(label=text, xalign=0)
    return css(widget, *classes)


def read_config():
    values = DEFAULTS.copy()
    if CONFIG.exists():
        try:
            for line in CONFIG.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith(("#", ";")):
                    key, value = line.split("=", 1)
                    key = key.strip()
                    if key in values:
                        values[key] = value.split("#", 1)[0].split(";", 1)[0].strip()
        except (OSError, UnicodeError) as error:
            return values, f"Não foi possível ler a configuração salva: {error}"
    return values, None


def save_config(rate, stage, dpis):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    existing = CONFIG.read_text(encoding="utf-8") if CONFIG.exists() else ""
    changed = {"polling_rate", "active_dpi", "dpis"}
    lines = [
        line for line in existing.splitlines()
        if not ("=" in line and line.split("=", 1)[0].strip() in changed)
    ]
    if not existing:
        lines = ["[general]"] + [
            f"{key} = {value}" for key, value in DEFAULTS.items() if key not in changed
        ]
    lines += [
        f"polling_rate = {rate}",
        f"active_dpi = {stage}",
        "dpis = " + " ".join(map(str, dpis)),
    ]
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=CONFIG.parent,
            prefix=".attack-shark-r1-", delete=False,
        ) as file:
            temp = Path(file.name)
            os.fchmod(file.fileno(), 0o600)
            file.write("\n".join(lines) + "\n")
        os.replace(temp, CONFIG)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def friendly_error(text, operation="battery"):
    detail = text.strip() or "O driver não retornou detalhes."
    if "Access denied" in detail or "insufficient permissions" in detail:
        return "Sem permissão para acessar o R1. Instale a regra udev do pacote e reconecte o mouse."
    if "Operation timed out" in detail or "Timeout" in detail:
        if operation == "battery":
            return "R1 detectado, mas sem resposta de bateria. Mova o mouse e tente atualizar novamente."
        return "O R1 não confirmou os ajustes no tempo esperado. Reconecte-o e tente aplicar novamente."
    if "No USB device" in detail or "not found" in detail.lower():
        return "R1 não encontrado. Verifique o cabo ou o receptor 2,4 GHz."
    return detail


class Dashboard(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Attack Shark R1")
        self.set_default_size(1160, 760)
        self.set_icon_name("attack-shark-r1")
        self.busy = False
        self.update_busy = False
        self.available_release = None
        self.rate = 1000
        self._build()
        GLib.idle_add(self.refresh_battery)

    def _build(self):
        values, config_warning = read_config()
        self.config_warning = config_warning
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_child(scroll)
        page = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22), "page")
        page.set_margin_top(28)
        page.set_margin_bottom(28)
        page.set_margin_start(28)
        page.set_margin_end(28)
        scroll.set_child(page)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        logo_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(APP_ICON), 56, 56, True)
        logo = Gtk.Picture.new_for_pixbuf(logo_pixbuf)
        logo.set_alternative_text("Ícone Attack Shark")
        logo.set_size_request(56, 56)
        logo.set_valign(Gtk.Align.CENTER)
        header.append(logo)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        titles.append(label("ATTACK SHARK  /  CONTROLE DO MOUSE", "brand"))
        titles.append(label("Seu R1, do seu jeito.", "heading"))
        titles.append(label("Ajuste a sensibilidade e a resposta do mouse.", "subheading"))
        header.append(titles)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)
        self.update_button = css(Gtk.Button(label="Verificar atualizações"), "secondary")
        self.update_button.set_valign(Gtk.Align.CENTER)
        self.update_button.connect("clicked", self.check_updates)
        header.append(self.update_button)
        self.device_badge = label("Verificando conexão", "badge")
        self.device_badge.set_valign(Gtk.Align.CENTER)
        header.append(self.device_badge)
        page.append(header)

        cards = Gtk.FlowBox()
        cards.set_selection_mode(Gtk.SelectionMode.NONE)
        cards.set_halign(Gtk.Align.CENTER)
        cards.set_column_spacing(18)
        cards.set_row_spacing(18)
        cards.set_min_children_per_line(1)
        cards.set_max_children_per_line(3)
        page.append(cards)
        cards.insert(self._dpi_card(values), -1)
        cards.insert(self._hero_card(), -1)
        cards.insert(self._status_card(values), -1)

        footer = css(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18), "glass")
        footer.set_margin_top(2)
        footer.set_margin_bottom(2)
        footer.set_margin_start(2)
        footer.set_margin_end(2)
        footer.set_size_request(-1, 78)
        footer.set_valign(Gtk.Align.CENTER)
        footer_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        footer_text.set_margin_start(20)
        footer_text.append(label("Pronto para configurar?", "section-title"))
        footer_text.append(label("Os ajustes só são enviados quando você clica em Aplicar.", "section-note"))
        footer.append(footer_text)
        filler = Gtk.Box()
        filler.set_hexpand(True)
        footer.append(filler)
        self.apply_button = css(Gtk.Button(label="Aplicar ao mouse"), "primary")
        self.apply_button.set_valign(Gtk.Align.CENTER)
        self.apply_button.set_margin_end(20)
        self.apply_button.connect("clicked", self.apply)
        footer.append(self.apply_button)
        page.append(footer)

        self.feedback = label(
            config_warning or "Pronto. Escolha os ajustes e clique em Aplicar ao mouse.", "feedback"
        )
        self.feedback.set_wrap(True)
        if config_warning:
            self.feedback.add_css_class("feedback-error")
        page.append(self.feedback)

    def _dpi_card(self, values):
        card = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12), "glass")
        card.set_size_request(270, 526)
        card.set_margin_top(4)
        card.set_margin_bottom(4)
        card.set_margin_start(4)
        card.set_margin_end(4)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        inner.set_margin_top(22)
        inner.set_margin_bottom(22)
        inner.set_margin_start(20)
        inner.set_margin_end(20)
        card.append(inner)
        inner.append(label("SENSIBILIDADE", "eyebrow"))
        inner.append(label("Perfis de DPI", "section-title"))
        inner.append(label("Seis níveis entre 100 e 18.000 DPI.", "section-note"))
        self.dpi_spins = []
        self.dpi_rows = []
        dpis = values["dpis"].split()
        if len(dpis) != 6:
            dpis = DEFAULTS["dpis"].split()
        for index, item in enumerate(dpis):
            row = css(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8), "profile-row")
            row.append(label(f"{index + 1:02d}", "number"))
            row_text = label(f"Perfil {index + 1}", "field-label")
            row_text.set_hexpand(True)
            row.append(row_text)
            spin = Gtk.SpinButton.new_with_range(100, 18000, 100)
            spin.set_numeric(True)
            spin.set_snap_to_ticks(True)
            spin.set_width_chars(6)
            try:
                spin.set_value(int(item))
            except ValueError:
                spin.set_value(int(DEFAULTS["dpis"].split()[index]))
            spin.set_tooltip_text(f"DPI do perfil {index + 1}, de 100 a 18000, em passos de 100")
            row.append(spin)
            self.dpi_spins.append(spin)
            self.dpi_rows.append(row)
            inner.append(row)
        inner.append(label("Perfil ativo", "field-label"))
        self.stage_dropdown = Gtk.DropDown.new_from_strings(
            [f"Perfil {i}" for i in range(1, 7)]
        )
        try:
            selected = max(0, min(5, int(values["active_dpi"]) - 1))
        except ValueError:
            selected = 2
        self.stage_dropdown.set_selected(selected)
        self.stage_dropdown.connect("notify::selected", self._stage_changed)
        inner.append(self.stage_dropdown)
        self._stage_changed()
        note = label("Seleção nesta tela. O mouse não informa seu perfil atual.", "section-note")
        note.set_wrap(True)
        note.set_max_width_chars(30)
        inner.append(note)
        return card

    def _hero_card(self):
        card = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8), "hero")
        card.set_size_request(380, 526)
        card.set_margin_top(4)
        card.set_margin_bottom(4)
        card.set_margin_start(4)
        card.set_margin_end(4)
        card.set_halign(Gtk.Align.CENTER)
        title = label("R1  /  USB + 2,4 GHZ", "eyebrow")
        title.set_margin_top(24)
        title.set_margin_start(24)
        card.append(title)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(MOUSE_IMAGE), 350, 350, True)
        art = Gtk.Picture.new_for_pixbuf(pixbuf)
        art.set_alternative_text("Mouse Attack Shark R1 preto visto de cima")
        art.set_content_fit(Gtk.ContentFit.CONTAIN)
        art.set_size_request(350, 400)
        art.set_halign(Gtk.Align.CENTER)
        art.set_vexpand(True)
        card.append(art)
        caption = label("ATTACK SHARK R1", "section-title")
        caption.set_halign(Gtk.Align.CENTER)
        caption.set_margin_bottom(24)
        card.append(caption)
        return card

    def _status_card(self, values):
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        side.set_size_request(270, 526)
        side.set_margin_top(4)
        side.set_margin_bottom(4)
        side.set_margin_start(4)
        side.set_margin_end(4)
        battery = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9), "glass")
        battery.set_size_request(270, 225)
        battery.set_margin_top(2)
        battery.set_margin_bottom(2)
        battery.set_margin_start(2)
        battery.set_margin_end(2)
        battery.append(self._inset(label("ENERGIA", "eyebrow"), top=20))
        battery.append(self._inset(label("Bateria", "section-title")))
        self.battery_value = label("—", "battery")
        battery.append(self._inset(self.battery_value))
        self.battery_note = label("Aguardando leitura", "section-note")
        battery.append(self._inset(self.battery_note))
        self.battery_button = css(Gtk.Button(label="Atualizar bateria"), "secondary")
        self.battery_button.set_margin_start(18)
        self.battery_button.set_margin_end(18)
        self.battery_button.set_margin_bottom(18)
        self.battery_button.connect("clicked", self.refresh_battery)
        battery.append(self.battery_button)
        side.append(battery)

        polling = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=13), "glass")
        polling.set_size_request(270, 280)
        polling.set_margin_top(2)
        polling.set_margin_bottom(2)
        polling.set_margin_start(2)
        polling.set_margin_end(2)
        polling.append(self._inset(label("RESPOSTA", "eyebrow"), top=20))
        polling.append(self._inset(label("Taxa de atualização", "section-title")))
        polling.append(self._inset(label("Selecione a frequência USB.", "section-note")))
        rate_grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        rate_grid.set_margin_start(18)
        rate_grid.set_margin_end(18)
        self.rate_buttons = {}
        try:
            self.rate = int(values["polling_rate"])
        except ValueError:
            self.rate = 1000
        for index, rate in enumerate((125, 250, 500, 1000)):
            button = css(Gtk.ToggleButton(label=f"{rate} Hz"), "rate")
            button.set_hexpand(True)
            button.connect("toggled", self._rate_toggled, rate)
            if self.rate_buttons:
                button.set_group(next(iter(self.rate_buttons.values())))
            self.rate_buttons[rate] = button
            rate_grid.attach(button, index % 2, index // 2, 1, 1)
        self.rate_buttons.get(self.rate, self.rate_buttons[1000]).set_active(True)
        polling.append(rate_grid)
        polling.append(self._inset(label("Taxas disponíveis: 125, 250, 500 e 1000 Hz.", "section-note")))
        side.append(polling)
        return side

    @staticmethod
    def _inset(widget, top=0):
        widget.set_margin_start(18)
        widget.set_margin_end(18)
        widget.set_margin_top(top)
        return widget

    def _rate_toggled(self, button, rate):
        if button.get_active():
            self.rate = rate

    def _stage_changed(self, *_):
        selected = self.stage_dropdown.get_selected()
        for index, row in enumerate(self.dpi_rows):
            if index == selected:
                row.add_css_class("profile-active")
            else:
                row.remove_css_class("profile-active")

    def _message(self, text, error=False):
        if self.config_warning:
            text = f"{self.config_warning}  {text}"
            error = True
        self.feedback.set_text(text)
        if error:
            self.feedback.add_css_class("feedback-error")
        else:
            self.feedback.remove_css_class("feedback-error")

    def _set_busy(self, busy):
        self.busy = busy
        self.apply_button.set_sensitive(not busy)
        self.battery_button.set_sensitive(not busy)

    def check_updates(self, *_):
        if self.update_busy:
            return False
        self.update_busy = True
        self.update_button.set_sensitive(False)
        if self.available_release:
            self._message("Baixando atualização e verificando integridade...")
            Thread(target=self._install_update_worker, daemon=True).start()
        else:
            self._message("Consultando atualizações no GitHub...")
            Thread(target=self._check_update_worker, daemon=True).start()
        return False

    def _check_update_worker(self):
        try:
            release = latest_release()
            newer = is_newer(installed_version(), release["version"] + "-1")
            GLib.idle_add(self._update_checked, release if newer else None, None)
        except Exception as error:
            GLib.idle_add(self._update_checked, None, str(error))

    def _update_checked(self, release, error):
        self.update_busy = False
        self.update_button.set_sensitive(True)
        if error:
            self._message("Não foi possível verificar atualizações: " + error, error=True)
        elif release:
            self.available_release = release
            self.update_button.set_label("Instalar v" + release["version"])
            self._message("Atualização v" + release["version"] + " disponível. Clique em Instalar para atualizar.")
        else:
            self._message("O aplicativo já está na versão mais recente.")
        return False

    def _install_update_worker(self):
        try:
            package = download_release(self.available_release)
            GLib.idle_add(self._message, "Pacote verificado. Autorize a instalação na janela do Ubuntu.")
            install_package(package)
            GLib.idle_add(self._update_installed, None)
        except Exception as error:
            GLib.idle_add(self._update_installed, str(error))

    def _update_installed(self, error):
        self.update_busy = False
        self.update_button.set_sensitive(True)
        if error:
            self._message("Atualização não instalada: " + error, error=True)
        else:
            self.available_release = None
            self.update_button.set_label("Verificar atualizações")
            self._message("Atualização instalada. Feche e abra o aplicativo novamente.")
        return False

    def refresh_battery(self, *_):
        if self.busy:
            return False
        self._set_busy(True)
        self.battery_note.set_text("Consultando...")
        self._message("Consultando a bateria do R1...")
        Thread(target=self._battery_worker, daemon=True).start()
        return False

    def _battery_worker(self):
        try:
            result = subprocess.run(
                [str(DRIVER), "--battery"], capture_output=True, text=True, timeout=8
            )
            GLib.idle_add(self._battery_finished, result.returncode, result.stdout, result.stderr)
        except (OSError, subprocess.TimeoutExpired) as error:
            GLib.idle_add(self._battery_finished, 1, "", str(error))

    def _battery_finished(self, code, output, error):
        self._set_busy(False)
        if code == 0:
            try:
                value = int(output.strip())
                if not 0 <= value <= 100:
                    raise ValueError("fora do intervalo")
            except ValueError:
                return self._battery_finished(1, "", "Resposta de bateria inválida do driver.")
            self.battery_value.set_text(f"{value}%")
            self.battery_note.set_text("Atualizada às " + datetime.now().strftime("%H:%M"))
            self.device_badge.set_text("R1 conectado")
            self.device_badge.remove_css_class("badge-error")
            self._message("Leitura da bateria concluída.")
        else:
            self.battery_value.set_text("—")
            self.battery_note.set_text("Leitura indisponível")
            if "Operation timed out" in error or "Timeout" in error:
                self.device_badge.set_text("R1 detectado")
                self.device_badge.remove_css_class("badge-error")
            else:
                self.device_badge.set_text("Conexão indisponível")
                self.device_badge.add_css_class("badge-error")
            self._message(friendly_error(error), error=True)
        return False

    def apply(self, *_):
        if self.busy:
            return
        dpis = [int(round(spin.get_value())) for spin in self.dpi_spins]
        if any(dpi < 100 or dpi > 18000 or dpi % 100 for dpi in dpis):
            self._message("Cada DPI deve ser múltiplo de 100, entre 100 e 18.000.", error=True)
            return
        stage = self.stage_dropdown.get_selected() + 1
        self._set_busy(True)
        self._message("Salvando e enviando configuração ao R1...")
        Thread(target=self._apply_worker, args=(self.rate, stage, dpis), daemon=True).start()

    def _apply_worker(self, rate, stage, dpis):
        try:
            save_config(rate, stage, dpis)
        except (OSError, UnicodeError) as error:
            GLib.idle_add(self._apply_finished, False, f"Não foi possível salvar: {error}")
            return
        try:
            result = subprocess.run(
                [str(DRIVER), "--apply-config"], capture_output=True, text=True, timeout=12
            )
            if result.returncode == 0:
                GLib.idle_add(self._apply_finished, True, "Comandos enviados ao R1. O dispositivo não oferece leitura de confirmação.")
            else:
                GLib.idle_add(
                    self._apply_finished, False,
                    "Configuração salva, mas aplicação não confirmada. " + friendly_error(result.stderr, "apply"),
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            GLib.idle_add(
                self._apply_finished, False, f"Configuração salva, mas aplicação não confirmada: {error}"
            )

    def _apply_finished(self, success, message):
        self._set_busy(False)
        if not message.startswith("Não foi possível salvar:"):
            self.config_warning = None
        self._message(message, error=not success)
        return False


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = Dashboard(self)
        window.present()


if __name__ == "__main__":
    raise SystemExit(App().run(None))
