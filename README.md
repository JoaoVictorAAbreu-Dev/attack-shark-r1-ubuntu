# Attack Shark R1 para Ubuntu

Aplicativo desktop GTK4 independente para o mouse Attack Shark R1. A versão 0.6.0
mostra o mouse em um dashboard e permite consultar a bateria, escolher seis
níveis de DPI (100 a 18.000, em passos de 100), o perfil ativo e a taxa USB
(125, 250, 500 ou 1000 Hz).

## Instalação

```bash
sudo dpkg -i ./attack-shark-r1_0.6.0_amd64.deb
```

Depois, desconecte e reconecte o receptor USB ou o cabo. Abra **Attack Shark R1**
no menu de aplicativos. O pacote instala uma regra udev restrita aos IDs
`1d57:fa60` (receptor) e `1d57:fa61` (cabo). O perfil de configuração fica em
`~/.config/attack-shark-r1.ini` (ou `$XDG_CONFIG_HOME/attack-shark-r1.ini`).
O pacote não substitui esse arquivo.

O botão **Aplicar ao mouse** grava o perfil no arquivo e envia os comandos ao
hardware. Se o envio falhar, o aplicativo informa que a configuração foi salva,
mas a aplicação não foi confirmada. A bateria é consultada ao abrir, a cada
30 segundos enquanto a janela estiver aberta e pelo botão **Atualizar**.
O ícone preenche até a porcentagem lida e anima a mudança. Quando uma leitura
real passa de menos de 100% para 100%, o app mostra **Carga completa** e envia
uma notificação ao Ubuntu. Uma leitura temporariamente indisponível fica marcada
como **Última leitura**.

O receptor 2,4 GHz informa porcentagem e estado de carregamento. No modo USB
com cabo, o driver atual não obtém um nível real: o app mostra **—** e não
declara o mouse carregado. A carga completa só pode ser confirmada por uma
leitura real do receptor. O monitoramento e a notificação funcionam enquanto
o aplicativo estiver aberto.
O destaque do perfil ativo representa a seleção na tela. Ela é salva ao clicar
em **Aplicar ao mouse**. O driver atual não lê de volta as configurações do dispositivo.

## Atualizações

Clique em **Verificar atualizações**. O aplicativo consulta a última versão
publicada em [GitHub Releases](https://github.com/JoaoVictorAAbreu-Dev/attack-shark-r1-ubuntu/releases),
baixa o pacote para o cache local e confere seu SHA-256 antes de instalar.
Clique em **Instalar** quando houver uma versão nova e autorize a janela de
administração do Ubuntu. Feche e reabra o aplicativo após a instalação.
Não é necessário baixar arquivos manualmente. A verificação é iniciada pelo
usuário; o aplicativo não instala atualizações sozinho.

## Limites e origem

O driver nativo deriva de
[jlucaso1/attack-shark-r1](https://github.com/jlucaso1/attack-shark-r1),
commit `ed6a4c1aa63f31471e26dd5dd7db533905b63ad9`
(MIT ou Apache-2.0). Foi acrescentado `--apply-config`; a interface GTK4 e o
empacotamento são novos. O instalador original fornecido contém apenas
executáveis Windows, sem código-fonte. O pacote não inclui esse instalador.
A logo enviada foi adaptada com OpenAI ImageGen para um ícone de aplicativo
com fundo externo transparente;
o mouse enviado anteriormente aparece no painel do dispositivo.

O layout usa superfícies sólidas, tipografia legível e uma barra
de ação fixa. A organização visual foi inspirada no
[Dashboard de Dwinawan no Figma](https://www.figma.com/community/file/1048559673287861086/dashboard/)
(CC BY 4.0); nenhuma imagem, componente ou código desse arquivo foi incorporado.

Ainda não há remapeamento de botões, macros, iluminação ou atualização de
firmware. Neste Ubuntu, a regra udev liberou o acesso USB. Uma consulta inicial
de bateria terminou em tempo limite; outra, com o mouse ativo, retornou 30%.
A aplicação de ajustes ao hardware ainda não foi confirmada em teste real.

O comando `/usr/lib/attack-shark-r1/attack-shark-r1 --battery-status` retorna
porcentagem e estado em JSON; no cabo, ambos são `null`. O comando legado
`--battery` retorna apenas o número e pode mostrar os 100% sintéticos no cabo.
Sem argumentos, o driver inicia o monitor contínuo de bateria
para UPower; esse monitor não é habilitado automaticamente pelo pacote e pode
exigir permissão separada para `/dev/uhid`.

## Desinstalação

```bash
sudo apt remove attack-shark-r1
```

A desinstalação remove o aplicativo e sua regra udev, preservando o arquivo de
configuração pessoal.
