# Código-fonte do aplicativo Ubuntu

- `app_gtk.py`: dashboard GTK4.
- `updater.py`: verificação de releases, checksum e instalação com autenticação do Ubuntu.
- `r1-native/`: driver Rust baseado em
  [jlucaso1/attack-shark-r1](https://github.com/jlucaso1/attack-shark-r1),
  commit `ed6a4c1aa63f31471e26dd5dd7db533905b63ad9`, com o comando
  `--apply-config`, `--battery-status` e regra udev de acesso restrito.
- `mouse.png`: imagem fornecida pelo usuário, usada no painel do dispositivo.
- `logo-original.png`: marca fornecida pelo usuário.
- `app-icon.png`: versão para o menu/dock produzida com o ImageGen integrado,
  editando a marca original. O fundo externo foi removido com uma máscara de
  transparência local que preserva os pixels do ícone. Prompt usado: "Edit the attached user-supplied black
  Attack Shark abstract shark-fin/A monogram into a polished Ubuntu/GNOME desktop
  application icon. Preserve the exact recognizable black angular monogram
  silhouette, proportions, cutout and orientation; do not invent a new logo.
  Center it large on an elegant rounded-square app tile with a soft warm
  ivory-to-cool-white surface, very subtle blue-gray depth/shadow and crisp
  edges, similar in visual weight and finish to modern installed GNOME
  application icons. No lettering, no words, no tiny badges, no mouse drawing,
  no border frame. Square 1:1 composition, icon remains legible at 48px.
  Opaque background."
- `build_deb.py`, `*.desktop`, `postinst`, `postrm`: empacotamento Debian.

Para reconstruir em Ubuntu 26.04 x86_64, instale Rust/Cargo, Python 3 com
PyGObject, GTK4 e GdkPixbuf, então execute `python3 build_deb.py`. O script
compila o driver se o binário local não existir e produz o pacote em `dist/`.
O driver oferece `--battery-status` em JSON, `--battery` legado e `--apply-config`.

O aplicativo depende dos componentes GTK4 do sistema. O pacote não inclui o
instalador Windows nem seu código.
