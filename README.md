# Claude Session Manager

App nativo GTK4/libadwaita para navegar e retomar sessões do Claude Code
salvas em `~/.claude/projects/`, de qualquer diretório do sistema.

Inspirado em [r4nd3l/agent-session-manager](https://github.com/r4nd3l/agent-session-manager).

## Rodar

```bash
python3 -m claude_session_manager
```

Dependência: PyGObject com GTK4 + libadwaita (`python3-gobject`, `gtk4`,
`libadwaita` — já presentes neste sistema).

### Instalar no menu de aplicativos

```bash
bash data/install.sh
```

Instala um `.desktop` + ícone em `~/.local/share/applications` e
`~/.local/share/icons` (sem sudo). Depois disso o app aparece no launcher
como "Claude Session Manager".

### Terminal embutido (opcional)

Por padrão, "Retomar" abre um terminal externo (konsole, gnome-terminal,
kitty, alacritty, wezterm, foot ou xterm — o primeiro encontrado no PATH)
já com `claude --resume <id>` rodando no diretório do projeto.

Se você instalar os bindings GTK4 do VTE:

```bash
sudo dnf install vte291-gtk4
```

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
- Favoritos (grupo próprio no topo) e nomes customizados, persistidos em
  `~/.config/claude-session-manager/state.json` — nunca nos arquivos do
  Claude.
- Busca ao vivo por nome, projeto, preview da primeira mensagem ou id da
  sessão.
- Clique/Enter numa sessão (ou botão ▶) retoma a sessão — embutida (VTE)
  ou em terminal externo, dependendo do que está disponível.
- Atualização automática a cada 5s.

## Variáveis de ambiente (dev/teste)

- `CSM_PROJECTS_DIR` — sobrepõe `~/.claude/projects` (útil para dados de demo).
- `CSM_STATE_DIR` — sobrepõe `~/.config/claude-session-manager`.

## Limitações conhecidas

- Sem replay de transcript, chat embutido ou multi-provider (Cursor etc.)
  — o `agent-session-manager` original cobre isso, se for necessário.
