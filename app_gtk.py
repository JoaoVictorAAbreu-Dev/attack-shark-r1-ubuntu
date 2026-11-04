#!/usr/bin/python3
"""Attack Shark R1 dashboard for Ubuntu (GTK 4)."""

import os
import json
from pathlib import Path
import subprocess
import tempfile
from threading import Lock, Thread
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk
from updater import download_release, install_package, installed_version, is_newer, latest_release
from usb_presence import scan_usb_modes


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
@define-color page_bg #f5f6f7;
@define-color surface #ffffff;
@define-color ink #18232e;
@define-color muted #485869;
@define-color line #dce2e7;
@define-color blue #254e84;
window { background: @page_bg; color: @ink; font-family: Cantarell, sans-serif; }
.app-shell, .page { background: @page_bg; }
.topbar, .actionbar { background: @surface; border-color: @line; }
.topbar { border-bottom: 1px solid @line; padding: 12px 28px; }
.actionbar { border-top: 1px solid @line; padding: 14px 28px; }
.brand-name { color: @ink; font-size: 17px; font-weight: 700; }
.brand-detail, .muted, .section-note { color: @muted; font-size: 12px; }
.page-title { color: @ink; font-size: 26px; font-weight: 700; }
.section-title { color: @ink; font-size: 18px; font-weight: 700; }
.field-label { color: @ink; font-size: 13px; font-weight: 600; }
.eyebrow { color: @muted; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
.panel { background: @surface; border: 1px solid @line; border-radius: 12px; }
.device-panel { background: #edf1f4; border: 1px solid #dce3e8; border-radius: 12px; }
.divider { background: @line; min-height: 1px; }
.product-name { color: @ink; font-size: 18px; font-weight: 700; }
.battery { color: @ink; font-size: 31px; font-weight: 700; }
.battery-state { color: @blue; font-size: 12px; font-weight: 700; }
.battery-full { color: #17603a; }
.battery-unknown { color: @muted; }
.battery-outline { border: 2px solid #4a5e73; border-radius: 5px; }
.battery-tip { background: #4a5e73; border-radius: 0 2px 2px 0; }
.battery-fill { background: #2b5987; border-radius: 2px; }
.battery-fill-charging { background: #2664a8; }
.battery-fill-low { background: #bf4930; }
.battery-fill-full { background: #1a7442; }
.badge { background: #e8f3ed; color: #185b38; border: 1px solid #b8d8c3;
         border-radius: 7px; padding: 7px 11px; font-size: 12px; font-weight: 700; }
.badge-error { background: #fff0ed; color: #94342e; border-color: #e8bdb8; }
.profile-row { border-bottom: 1px solid #e8ecef; padding: 6px 10px; }
.profile-active { background: #ebf2fb; border-radius: 6px; }
.number { color: #586b7e; font-size: 12px; font-weight: 700; }
spinbutton, spinbutton text, dropdown, dropdown button { background: @surface; color: @ink;
    border: 1px solid #8699aa; border-radius: 6px; min-height: 36px; }
spinbutton button { background: #f6f8fa; color: @ink; }
spinbutton:focus-within, dropdown:focus { border-color: @blue; }
button.rate { background: @surface; color: @ink; border: 1px solid #8699aa;
              border-radius: 6px; min-height: 38px; font-weight: 600; }
button.rate:checked { background: @blue; color: #ffffff; border-color: @blue; }
button.rate:checked label { color: #ffffff; }
button.rate:focus, button:focus, spinbutton:focus-within, dropdown:focus { outline: 2px solid @blue; outline-offset: 2px; }
button.primary { background: #1c354d; color: #ffffff; border-radius: 7px;
                 min-height: 42px; padding: 0 20px; font-weight: 700; }
button.primary label { color: #ffffff; }
button.primary:hover { background: #294b69; }
button.primary:disabled { background: #7d8d9d; }
button.secondary { background: @surface; color: @ink; border: 1px solid #8699aa;
                   border-radius: 7px; min-height: 36px; padding: 0 12px; font-weight: 600; }
button.secondary:hover { background: #eef2f5; }
button.secondary label { color: @ink; }
.feedback { color: #304355; font-size: 12px; }
.feedback-error { color: #9b3931; }
"""


def css(widget, *names):
    for name in names:
        widget.add_css_class(name)
    return widget


def label(text, *classes):
    widget = Gtk.Label(label=text, xalign=0)
    return css(widget, *classes)


def picture(path, width, height, description):
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), width, height, True)
    widget = Gtk.Picture.new_for_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
    widget.set_alternative_text(description)
    widget.set_content_fit(Gtk.ContentFit.CONTAIN)
    widget.set_size_request(width, height)
    return widget


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


def render_config(rate, stage, dpis):
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
    return "\n".join(lines) + "\n"


def save_config(rate, stage, dpis):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    content = render_config(rate, stage, dpis)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=CONFIG.parent,
            prefix=".attack-shark-r1-", delete=False,
        ) as file:
            temp = Path(file.name)
            os.fchmod(file.fileno(), 0o600)
            file.write(content)
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


def parse_battery_status(output):
    try:
        status = json.loads(output)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError("Resposta de bateria inválida do driver.") from error
    if not isinstance(status, dict) or type(status.get("wired")) is not bool:
        raise ValueError("Resposta de bateria inválida do driver.")
    percentage = status.get("percentage")
    charging = status.get("charging")
    if status["wired"]:
        if percentage is not None or charging is not None:
            raise ValueError("Leitura por cabo sem estado confiável.")
        return None, None, True
    if type(percentage) is not int or not 0 <= percentage <= 100 or type(charging) is not bool:
        raise ValueError("Resposta de bateria inválida do driver.")
    return percentage, charging, False


class Dashboard(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Attack Shark R1")
        self.set_default_size(1160, 760)
        self.set_size_request(680, 520)
        self.set_icon_name("attack-shark-r1")
        self.busy = False
        self.battery_busy = False
        self.device_ready = False
        self.present_modes = object()
        self.connection_generation = 0
        self.device_lock = Lock()
        self.battery_percentage = None
        self.battery_display = 0.0
        self.battery_charging = None
        self.battery_wired = False
        self.battery_animation_source = None
        self.full_notified = False
        self.last_battery_time = None
        self.update_busy = False
        self.available_release = None
        self.rate = 1000
        self._build()
        self._connection_timer()
        GLib.timeout_add_seconds(2, self._connection_timer)
        GLib.timeout_add_seconds(30, self._battery_timer)

    def _build(self):
        values, self.config_warning = read_config()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        shell = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), "app-shell")
        self.set_child(shell)

        header = css(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12), "topbar")
        shell.append(header)
        logo = picture(APP_ICON, 44, 44, "Ícone Attack Shark")
        logo.set_valign(Gtk.Align.CENTER)
        header.append(logo)
        identity = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        identity.append(label("Attack Shark R1", "brand-name"))
        identity.append(label("Configuração do mouse", "brand-detail"))
        header.append(identity)
        space = Gtk.Box()
        space.set_hexpand(True)
        header.append(space)
        self.device_badge = label("Verificando conexão", "badge")
        self.device_badge.set_valign(Gtk.Align.CENTER)
        header.append(self.device_badge)
        self.update_button = css(Gtk.Button(label="Verificar atualizações"), "secondary")
        self.update_button.set_valign(Gtk.Align.CENTER)
        self.update_button.connect("clicked", self.check_updates)
        header.append(self.update_button)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        shell.append(scroll)
        page = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18), "page")
        page.set_margin_top(24)
        page.set_margin_bottom(24)
        page.set_margin_start(24)
        page.set_margin_end(24)
        scroll.set_child(page)
        intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        intro.append(label("Configurações", "page-title"))
        intro.append(label("Ajuste os perfis de DPI e a taxa USB do R1.", "muted"))
        page.append(intro)

        columns = Gtk.FlowBox()
        columns.set_selection_mode(Gtk.SelectionMode.NONE)
        columns.set_halign(Gtk.Align.CENTER)
        columns.set_column_spacing(18)
        columns.set_row_spacing(18)
        columns.set_min_children_per_line(1)
        columns.set_max_children_per_line(2)
        columns.insert(self._device_panel(), -1)
        columns.insert(self._settings_panel(values), -1)
        page.append(columns)

        footer = css(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24), "actionbar")
        shell.append(footer)
        self.feedback = label(
            self.config_warning or "Escolha os ajustes e clique em Aplicar ao mouse.", "feedback"
        )
        self.feedback.set_hexpand(True)
        self.feedback.set_wrap(True)
        if self.config_warning:
            self.feedback.add_css_class("feedback-error")
        footer.append(self.feedback)
        self.apply_button = css(Gtk.Button(label="Aplicar ao mouse"), "primary")
        self.apply_button.set_valign(Gtk.Align.CENTER)
        self.apply_button.connect("clicked", self.apply)
        self.apply_button.set_sensitive(False)
        footer.append(self.apply_button)

    def _device_panel(self):
        panel = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0), "device-panel")
        panel.set_size_request(300, 430)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_margin_top(20)
        inner.set_margin_bottom(20)
        inner.set_margin_start(20)
        inner.set_margin_end(20)
        panel.append(inner)
        inner.append(label("DISPOSITIVO  /  R1", "eyebrow"))
        art = picture(MOUSE_IMAGE, 260, 210, "Mouse Attack Shark R1 preto visto de cima")
        art.set_halign(Gtk.Align.CENTER)
        inner.append(art)
        inner.append(label("Attack Shark R1", "product-name"))
        inner.append(label("USB ou receptor 2,4 GHz", "muted"))
        divider = css(Gtk.Box(), "divider")
        divider.set_margin_top(10)
        divider.set_margin_bottom(4)
        inner.append(divider)
        battery_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        battery_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        battery_text.set_hexpand(True)
        battery_text.append(label("BATERIA", "eyebrow"))
        readout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        readout.set_valign(Gtk.Align.CENTER)
        icon = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        icon.set_valign(Gtk.Align.CENTER)
        icon.set_tooltip_text("Nível de bateria do R1")
        frame = css(Gtk.Fixed(), "battery-outline")
        frame.set_size_request(52, 26)
        self.battery_fill = css(Gtk.Box(), "battery-fill")
        self.battery_fill.set_size_request(0, 18)
        self.battery_fill.set_visible(False)
        frame.put(self.battery_fill, 4, 4)
        icon.append(frame)
        tip = css(Gtk.Box(), "battery-tip")
        tip.set_size_request(5, 12)
        icon.append(tip)
        readout.append(icon)
        self.battery_value = label("—", "battery")
        readout.append(self.battery_value)
        battery_text.append(readout)
        battery_line.append(battery_text)
        self.battery_button = css(Gtk.Button(label="Atualizar"), "secondary")
        self.battery_button.set_tooltip_text("Consultar a bateria do R1")
        self.battery_button.set_valign(Gtk.Align.END)
        self.battery_button.connect("clicked", self.refresh_battery)
        battery_line.append(self.battery_button)
        inner.append(battery_line)
        self.battery_state = label("Aguardando leitura", "battery-state", "battery-unknown")
        inner.append(self.battery_state)
        self.battery_note = label("Aguardando leitura", "section-note")
        self.battery_note.set_wrap(True)
        inner.append(self.battery_note)
        return panel

    def _settings_panel(self, values):
        panel = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), "panel")
        panel.set_size_request(600, 500)
        panel.set_hexpand(True)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_margin_top(22)
        inner.set_margin_bottom(22)
        inner.set_margin_start(24)
        inner.set_margin_end(24)
        panel.append(inner)
        inner.append(label("Sensibilidade", "section-title"))
        inner.append(label("Seis perfis · 100 a 18.000 DPI, em passos de 100.", "section-note"))

        self.dpi_spins = []
        self.dpi_rows = []
        dpis = values["dpis"].split()
        if len(dpis) != 6:
            dpis = DEFAULTS["dpis"].split()
        for index, item in enumerate(dpis):
            row = css(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10), "profile-row")
            row.set_size_request(-1, 43)
            number = label(f"{index + 1:02d}", "number")
            number.set_size_request(26, -1)
            row.append(number)
            row_text = label(f"Perfil {index + 1}", "field-label")
            row_text.set_hexpand(True)
            row.append(row_text)
            spin = Gtk.SpinButton.new_with_range(100, 18000, 100)
            spin.set_numeric(True)
            spin.set_snap_to_ticks(True)
            spin.set_width_chars(5)
            spin.set_size_request(122, -1)
            try:
                spin.set_value(int(item))
            except ValueError:
                spin.set_value(int(DEFAULTS["dpis"].split()[index]))
            spin.set_tooltip_text(f"DPI do perfil {index + 1}, de 100 a 18000, em passos de 100")
            row.append(spin)
            self.dpi_spins.append(spin)
            self.dpi_rows.append(row)
            inner.append(row)

        profile_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        profile_line.set_margin_top(8)
        profile_label = label("Perfil ativo", "field-label")
        profile_label.set_hexpand(True)
        profile_line.append(profile_label)
        self.stage_dropdown = Gtk.DropDown.new_from_strings([f"Perfil {i}" for i in range(1, 7)])
        self.stage_dropdown.set_size_request(160, -1)
        try:
            selected = max(0, min(5, int(values["active_dpi"]) - 1))
        except ValueError:
            selected = 2
        self.stage_dropdown.set_selected(selected)
        self.stage_dropdown.connect("notify::selected", self._stage_changed)
        profile_line.append(self.stage_dropdown)
        inner.append(profile_line)
        self._stage_changed()
        note = label("A seleção é salva ao aplicar; o R1 não informa o perfil atual.", "section-note")
        note.set_wrap(True)
        inner.append(note)

        divider = css(Gtk.Box(), "divider")
        divider.set_margin_top(10)
        divider.set_margin_bottom(10)
        inner.append(divider)
        inner.append(label("Taxa USB", "section-title"))
        inner.append(label("Escolha a frequência de resposta do mouse.", "section-note"))
        rates = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        rates.set_margin_top(5)
        self.rate_buttons = {}
        try:
            self.rate = int(values["polling_rate"])
        except ValueError:
            self.rate = 1000
        for rate in (125, 250, 500, 1000):
            button = css(Gtk.ToggleButton(label=f"{rate} Hz"), "rate")
            button.set_hexpand(True)
            button.connect("toggled", self._rate_toggled, rate)
            if self.rate_buttons:
                button.set_group(next(iter(self.rate_buttons.values())))
            self.rate_buttons[rate] = button
            rates.append(button)
        self.rate_buttons.get(self.rate, self.rate_buttons[1000]).set_active(True)
        inner.append(rates)
        return panel

    def _update_battery_fill(self):
        level = max(0.0, min(100.0, self.battery_display))
        self.battery_fill.set_visible(self.battery_percentage is not None and level > 0)
        self.battery_fill.set_size_request(round(42 * level / 100), 18)
        for style in ("battery-fill-charging", "battery-fill-low", "battery-fill-full"):
            self.battery_fill.remove_css_class(style)
        if self.battery_percentage == 100:
            self.battery_fill.add_css_class("battery-fill-full")
        elif self.battery_percentage is not None and self.battery_percentage <= 20:
            self.battery_fill.add_css_class("battery-fill-low")
        elif self.battery_charging:
            self.battery_fill.add_css_class("battery-fill-charging")

    def _animate_battery(self, percentage):
        if self.battery_animation_source is not None:
            GLib.source_remove(self.battery_animation_source)
            self.battery_animation_source = None
        start = self.battery_display if self.battery_percentage is not None else 0.0
        self.battery_percentage = percentage
        if abs(start - percentage) < 0.2:
            self.battery_display = float(percentage)
            self._update_battery_fill()
            return
        self.battery_animation_from = start
        self.battery_animation_target = float(percentage)
        self.battery_animation_start = GLib.get_monotonic_time()
        self.battery_animation_source = GLib.timeout_add(16, self._battery_animation_step)

    def _battery_animation_step(self):
        elapsed = (GLib.get_monotonic_time() - self.battery_animation_start) / 600_000
        progress = min(1.0, elapsed)
        eased = 1 - (1 - progress) ** 3
        self.battery_display = self.battery_animation_from + (
            self.battery_animation_target - self.battery_animation_from
        ) * eased
        self._update_battery_fill()
        if progress >= 1:
            self.battery_animation_source = None
            return False
        return True

    def _clear_battery(self):
        if self.battery_animation_source is not None:
            GLib.source_remove(self.battery_animation_source)
            self.battery_animation_source = None
        self.battery_percentage = None
        self.battery_display = 0.0
        self._update_battery_fill()

    def _battery_timer(self):
        self.refresh_battery(silent=True)
        return True

    def _set_presence(self, modes):
        self.present_modes = modes
        self.connection_generation += 1
        self.device_ready = False
        self.battery_busy = False
        self.battery_charging = None
        self.full_notified = False
        self.last_battery_time = None
        self._clear_battery()
        self.battery_value.set_text("—")
        self.battery_state.remove_css_class("battery-full")
        self.battery_state.add_css_class("battery-unknown")
        self.device_badge.remove_css_class("badge-error")
        if modes == frozenset():
            self.device_badge.set_text("R1 desconectado")
            self.device_badge.add_css_class("badge-error")
            self.battery_state.set_text("Desconectado")
            self.battery_note.set_text("Conecte o cabo ou o receptor 2,4 GHz.")
            self._message("R1 desconectado. Conecte-o para aplicar ajustes.", error=True)
        elif modes is None:
            self.device_badge.set_text("Verificando conexão")
            self.battery_state.set_text("Leitura indisponível")
            self.battery_note.set_text("Não foi possível verificar a conexão USB.")
        else:
            self.device_badge.set_text("Cabo e receptor detectados" if len(modes) == 2 else
                                       "Cabo detectado" if "wired" in modes else "Receptor detectado")
            self.battery_state.set_text("Verificando mouse")
            self.battery_note.set_text("Consultando o R1...")
        self._set_busy(self.busy)

    def _connection_timer(self):
        modes = scan_usb_modes()
        if modes != self.present_modes:
            self._set_presence(modes)
            if modes is None or modes:
                self.refresh_battery(silent=True)
        return True

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
        self.apply_button.set_sensitive(not busy and self.device_ready)
        self.battery_button.set_sensitive(
            not busy and not self.battery_busy and self.present_modes != frozenset()
        )

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

    def refresh_battery(self, *_, silent=False):
        modes = scan_usb_modes()
        if modes != self.present_modes:
            self._set_presence(modes)
        if modes == frozenset():
            return False
        if self.busy or self.battery_busy:
            return False
        self.battery_busy = True
        self.battery_button.set_sensitive(False)
        if not silent:
            self.battery_note.set_text("Consultando...")
            self._message("Consultando a bateria do R1...")
        Thread(target=self._battery_worker, args=(silent, self.connection_generation), daemon=True).start()
        return False

    def _battery_worker(self, silent, generation):
        try:
            with self.device_lock:
                result = subprocess.run(
                    [str(DRIVER), "--battery-status"], capture_output=True, text=True, timeout=8
                )
            GLib.idle_add(self._battery_finished, result.returncode, result.stdout, result.stderr, silent, generation)
        except (OSError, subprocess.TimeoutExpired) as error:
            GLib.idle_add(self._battery_finished, 1, "", str(error), silent, generation)

    def _battery_finished(self, code, output, error, silent=False, generation=None):
        if generation is not None and generation != self.connection_generation:
            return False
        modes = scan_usb_modes()
        if modes != self.present_modes:
            self._set_presence(modes)
            if modes is None or modes:
                self.refresh_battery(silent=True)
            return False
        self.battery_busy = False
        self._set_busy(self.busy)
        if code == 0:
            try:
                value, charging, wired = parse_battery_status(output)
            except ValueError as problem:
                code, error = 1, str(problem)
            else:
                if modes is not None and ((wired and "wired" not in modes) or
                                              (not wired and "receiver" not in modes)):
                    self._set_presence(modes)
                    self.refresh_battery(silent=True)
                    return False
                self.device_ready = True
                self._set_busy(self.busy)
                self.battery_wired = wired
                self.device_badge.set_text("R1 por cabo" if wired else "R1 conectado")
                self.device_badge.remove_css_class("badge-error")
                self.battery_state.remove_css_class("battery-full")
                self.battery_state.remove_css_class("battery-unknown")
                if wired:
                    self._clear_battery()
                    self.battery_charging = None
                    self.battery_value.set_text("—")
                    self.battery_state.set_text("Cabo conectado")
                    self.battery_state.add_css_class("battery-unknown")
                    self.battery_note.set_text("Carga não informada pelo modo USB.")
                    if not silent:
                        self._message("O R1 está por cabo; o driver não lê a carga nesse modo.")
                else:
                    previous = self.battery_percentage
                    self.battery_charging = charging
                    self._animate_battery(value)
                    self.battery_value.set_text(f"{value}%")
                    self.last_battery_time = datetime.now().strftime("%H:%M")
                    self.battery_note.set_text("Atualizada às " + self.last_battery_time)
                    if value == 100:
                        self.battery_state.set_text("Carga completa")
                        self.battery_state.add_css_class("battery-full")
                        if previous is not None and previous < 100 and not self.full_notified:
                            notice = Gio.Notification.new("R1 carregado")
                            notice.set_body("A bateria do mouse chegou a 100%.")
                            self.get_application().send_notification("r1-battery-full", notice)
                            self.full_notified = True
                    elif charging:
                        self.battery_state.set_text("Carregando")
                        self.full_notified = False
                    else:
                        self.battery_state.set_text("Em uso")
                        self.battery_state.add_css_class("battery-unknown")
                        self.full_notified = False
                    if not silent:
                        self._message("Leitura da bateria concluída.")
                return False
        if code != 0:
            timeout = "Operation timed out" in error or "Timeout" in error
            previous = self.battery_percentage
            previous_time = self.last_battery_time
            self.device_ready = False
            self._set_busy(self.busy)
            self._clear_battery()
            self.battery_value.set_text("—")
            self.battery_state.remove_css_class("battery-full")
            self.battery_state.add_css_class("battery-unknown")
            self.battery_state.set_text("Mouse sem resposta" if timeout else "Leitura indisponível")
            self.battery_note.set_text(
                f"Última leitura: {previous}% às {previous_time}. Mova o mouse e atualize."
                if timeout and previous is not None and previous_time else
                "Mova o mouse e tente atualizar." if timeout else
                "Verifique a conexão e tente novamente."
            )
            if timeout:
                self.device_badge.set_text("Receptor sem resposta" if modes and "receiver" in modes and "wired" not in modes
                                           else "Cabo sem resposta" if modes and "wired" in modes
                                           else "Conexão sem resposta")
                self.device_badge.add_css_class("badge-error")
            else:
                self.device_badge.set_text("Sem permissão" if "Access denied" in error or "insufficient permissions" in error
                                           else "Conexão indisponível")
                self.device_badge.add_css_class("badge-error")
            if not silent:
                self._message(friendly_error(error), error=True)
        return False

    def apply(self, *_):
        if self.busy:
            return
        if not self.device_ready or scan_usb_modes() == frozenset():
            self._connection_timer()
            self._message("Conecte o R1 e aguarde a confirmação antes de aplicar ajustes.", error=True)
            return
        dpis = [int(round(spin.get_value())) for spin in self.dpi_spins]
        if any(dpi < 100 or dpi > 18000 or dpi % 100 for dpi in dpis):
            self._message("Cada DPI deve ser múltiplo de 100, entre 100 e 18.000.", error=True)
            return
        stage = self.stage_dropdown.get_selected() + 1
        self._set_busy(True)
        self._message("Enviando configuração ao R1...")
        Thread(target=self._apply_worker, args=(self.rate, stage, dpis, self.present_modes), daemon=True).start()

    def _apply_worker(self, rate, stage, dpis, start_modes=None):
        try:
            content = render_config(rate, stage, dpis)
        except (OSError, UnicodeError) as error:
            GLib.idle_add(self._apply_finished, False, f"Não foi possível preparar a configuração: {error}")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="attack-shark-r1-") as directory:
                path = Path(directory) / "attack-shark-r1.ini"
                path.write_text(content, encoding="utf-8")
                path.chmod(0o600)
                with self.device_lock:
                    result = subprocess.run(
                        [str(DRIVER), "--apply-config", str(path)],
                        capture_output=True, text=True, timeout=12,
                    )
            if result.returncode == 0:
                if start_modes is not None and scan_usb_modes() != start_modes:
                    GLib.idle_add(self._apply_finished, False,
                                  "A conexão mudou durante o envio. Perfil anterior preservado; alguns ajustes podem ter sido aplicados.")
                    return
                try:
                    save_config(rate, stage, dpis)
                except (OSError, UnicodeError) as error:
                    GLib.idle_add(self._apply_finished, False,
                                  f"Comandos enviados, mas não foi possível salvar o perfil: {error}")
                else:
                    GLib.idle_add(self._apply_finished, True,
                                  "Comandos enviados ao R1 e perfil salvo. O dispositivo não oferece leitura de confirmação.")
            else:
                GLib.idle_add(
                    self._apply_finished, False,
                    "Perfil anterior preservado. Aplicação não confirmada: " + friendly_error(result.stderr, "apply"),
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            GLib.idle_add(
                self._apply_finished, False, f"Perfil anterior preservado. Aplicação não confirmada: {error}"
            )

    def _apply_finished(self, success, message):
        self._set_busy(False)
        if success:
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
