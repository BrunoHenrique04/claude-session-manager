# Claude Session Manager

App nativo GTK4/libadwaita para navegar e retomar sessões do Claude Code
salvas em `~/.claude/projects/`, de qualquer diretório do sistema.

Inspirado em [r4nd3l/agent-session-manager](https://github.com/r4nd3l/agent-session-manager).

## Plataforma

**Linux desktop, só isso.** É GTK4/libadwaita de verdade — entrada `.desktop`,
tema de ícones XDG, terminal embutido via VTE — nada disso existe fora do
Linux. `install.sh` é testado/simulado nas famílias principais:

| Distro                                   | Gerenciador de pacotes p/ VTE | Testado |
|-------------------------------------------|-------------------------------|---------|
| Fedora / RHEL / CentOS                    | `dnf`                         | ✅ instalação real (Bazzite, base Fedora) |
| Bazzite / Silverblue / Kinoite (atômicos) | `rpm-ostree` (+ reboot)       | ✅ instalação real |
| Ubuntu 24.04                              | `apt`                         | ✅ instalação real (container limpo, usuário sem privilégios) |
| Debian 12                                 | `apt`                         | ✅ instalação real (container limpo, usuário sem privilégios) |
| Arch / Manjaro / EndeavourOS              | `pacman`                      | ⚙️ simulado |
| openSUSE (Leap/Tumbleweed)                | `zypper`                      | ⚙️ simulado |
| openSUSE MicroOS/Aeon/Kalpa (atômicos)    | `transactional-update` (+ reboot) | ⚙️ simulado |
| Alpine, Void, NixOS                       | `apk` / `xbps` / `nix`        | ⚙️ simulado |

"Instalação real" = `install.sh` rodado de ponta a ponta (instalar,
conferir os arquivos no lugar certo, desinstalar) num container limpo
daquela distro, como usuário sem privilégios — Fedora/Bazzite numa
máquina de verdade, Ubuntu e Debian em containers (`podman`). "Simulado"
= só a lógica de detecção de distro (`depcheck.py`) foi testada, com
`/etc/os-release` sintético — não tenho VM/container fácil pra essas
agora. `install.sh` em si não tem nada específico de distro (bash +
paths XDG genéricos), então o padrão esperado é que funcione igual nas
que só foram simuladas também; a única parte que varia é a *sugestão* de
comando pra instalar o VTE, que é só um aviso — sem ele o app cai pra
terminal externo, a instalação principal não trava.

**Windows não é suportado** e não vai funcionar: `install.sh` é um script
bash (Windows não roda `.sh` nativamente), e mesmo contornando isso com
WSL, faltam GTK4 + libadwaita com build funcional pra Windows, VTE, e o
conceito inteiro de `.desktop`/tema de ícones XDG que o instalador usa.
Não é uma limitação de portar o código — é a plataforma de UI (GTK4/
libadwaita) e o mecanismo de menu (XDG) sendo Linux-only por natureza.

## Instalar (rápido)

```bash
./install.sh
```

Sem sudo, tudo em paths do usuário. Isso:

- checa as dependências (GTK4 + libadwaita; avisa sobre VTE se faltar,
  com o comando certo pro seu sistema — inclusive `rpm-ostree` em
  distros imutáveis como Bazzite/Silverblue/Kinoite, em vez de sugerir
  `dnf` num lugar onde isso não funciona);
- cria o comando `claude-session-manager` em `~/.local/bin` (symlink pra
  este diretório — `git pull` atualiza sem precisar reinstalar);
- instala o `.desktop` + ícone no menu de aplicativos.

Pra desinstalar: `./install.sh --uninstall` (mantém favoritos/projetos em
`~/.config/claude-session-manager`, a menos que você apague a pasta também).

## Rodar sem instalar

```bash
python3 -m claude_session_manager
```

Dependência: PyGObject com GTK4 + libadwaita (`python3-gobject`, `gtk4`,
`libadwaita` — já presentes neste sistema).

### Terminal embutido (opcional)

Por padrão, "Retomar" abre um terminal externo (konsole, gnome-terminal,
kitty, alacritty, wezterm, foot ou xterm — o primeiro encontrado no PATH)
já com `claude --resume <id>` rodando no diretório do projeto.

Se você instalar os bindings GTK4 do VTE (`./install.sh` já te diz o
comando certo pro seu sistema — `dnf`, `rpm-ostree`, `apt` ou `pacman`),
o app detecta automaticamente na próxima abertura e passa a abrir cada
sessão numa aba de terminal embutida (`Adw.TabView`), num painel ao lado
da lista, em vez de um terminal externo.

## O que faz

- Descobre sessões varrendo `~/.claude/projects/*/*.jsonl` (sem tocar nos
  dados do Claude).
- Visual em cards: título/caminho no topo, chips coloridos com **modelo
  usado** (ex. "Sonnet 5") e **% de contexto consumido** (com barrinha e cor
  que muda de verde → amarelo → vermelho conforme se aproxima do limite da
  janela de contexto do modelo).
- Marca sessões **aguardando sua resposta** (última mensagem do Claude foi
  uma pergunta) ou **interrompidas**, com um ícone na linha.
- **Projetos customizados**: crie um projeto (ex.: "API", "Frontend",
  "Docs") e atribua sessões de pastas/repositórios diferentes a ele pelo
  ícone 🏷 em cada linha — útil quando o mesmo produto tem sessões em
  vários diretórios. Sessões sem projeto continuam agrupadas por pasta.
- **Contexto entre sessões, mas só dentro de um projeto** (ícone 🔗 no
  cabeçalho do grupo): o Claude Code tem seu próprio esquema global de
  memória entre sessões, que nem sempre é desejável. Isso é uma versão
  no escopo do projeto — quando ligado, cada sessão retomada recebe um
  resumo curto das outras sessões do mesmo projeto (título, pasta, do
  que tratam) via `--append-system-prompt`, e as pastas delas ficam
  acessíveis via `--add-dir`. Desligado por padrão; nunca atravessa
  projetos diferentes.
- Grupos (Favoritos, projetos, pastas) são recolhíveis — clique no
  cabeçalho para esconder a lista; fica salvo entre reinicializações.
  Uma busca ativa sempre reabre um grupo recolhido que tiver resultado.
- Favoritos (grupo próprio no topo) e nomes customizados, persistidos em
  `~/.config/claude-session-manager/state.json` — nunca nos arquivos do
  Claude.
- Busca ao vivo por nome, projeto, preview da primeira mensagem ou id da
  sessão.
- Clique/Enter numa sessão (ou botão ▶) retoma a sessão — embutida (VTE)
  ou em terminal externo, dependendo do que está disponível. A seta ao
  lado do ▶ deixa escolher explicitamente: padrão ou modo perigoso
  (`--dangerously-skip-permissions`), cada um aqui no app ou em terminal
  externo.
- **Botão direito numa sessão** abre um menu com mais ações: abrir a
  pasta da sessão no gerenciador de arquivos, copiar id/caminho,
  favoritar, renomear e **excluir a sessão** (apaga o `.jsonl` do disco,
  com confirmação — não tem como desfazer).
- Atualização automática a cada 5s.

## Variáveis de ambiente (dev/teste)

- `CSM_PROJECTS_DIR` — sobrepõe `~/.claude/projects` (útil para dados de demo).
- `CSM_STATE_DIR` — sobrepõe `~/.config/claude-session-manager`.

## Limitações conhecidas

- Sem replay de transcript, chat embutido ou multi-provider (Cursor etc.)
  — o `agent-session-manager` original cobre isso, se for necessário.
