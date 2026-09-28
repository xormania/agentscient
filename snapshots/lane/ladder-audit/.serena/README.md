# .serena — Serena on this checkout

Serena is pinned by commit in `.mcp.json` and started by the harness
per session over stdio. Everything Serena owns for this checkout lives
under `.serena/home/` (gitignored), set by `SERENA_HOME` in `.mcp.json`,
so it never shares a config, a projects list, or a language-server
download with any other Serena install on the machine.

- `project.yml` is tracked and **normalized by Serena on every start**:
  it rewrites the file with every key and its own comments. Edit the
  values, not the comments, and expect the next start to reformat it.
  The committed form is what a start produces, so a start is a no-op.
- The PHP server is Phpactor (`php_phpactor`): needs only `php`, downloads
  a 4.4 MB phar into `home/language_servers/static/PhpactorServer/`.
  Intelephense would need node and npm, which this host does not have.
- Phpactor's Symfony extension is enabled by the tracked `.phpactor.json`
  at the repository root and reads the compiled dev container at
  `var/cache/dev/App_KernelDevDebugContainer.xml` (`composer install` and
  any `bin/console` run produce it). Phpactor loads a local config only
  from a trusted path, and trust is per absolute path in
  `~/.local/share/phpactor/trust.json`, so **each new worktree runs once**:

      php .serena/home/language_servers/static/PhpactorServer/phpactor.phar config:trust --trust

  (after the first session start has downloaded the phar). Until then the
  server still works; it just does not see the container.
- Roster under the `claude-code` context with this project file: 15 tools —
  the symbol readers and editors, the regex editors, file diagnostics,
  `initial_instructions`, and `restart_language_server` (use it after a
  hook or fixer reformats a file behind the server's buffer). Memories,
  onboarding, shell and whole-file tools are off.
- `ops/`, `.dev/`, `.xor/`, `.serena/` and everything gitignored are
  invisible to Serena's tools; the PHP server ignores `vendor/` by name.
