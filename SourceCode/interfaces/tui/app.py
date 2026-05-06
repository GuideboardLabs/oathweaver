from __future__ import annotations

from pathlib import Path

from .command_router import TUICommandRouter


def _run_plain_repl(repo_root: Path) -> None:
    router = TUICommandRouter(repo_root)
    print("Oathweaver Unified TUI (plain mode)")
    print("Type /help for commands. /quit to exit.")
    while True:
        try:
            text = input("oathweaver> ").strip()
        except EOFError:
            break
        if not text:
            continue
        out = router.dispatch(text)
        if out.text == "QUIT":
            break
        if out.error:
            print(f"ERROR: {out.text}")
        else:
            print(out.text)


def _run_textual(repo_root: Path) -> None:
    from textual import on
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.events import Mount
    from textual.widgets import Footer, Header, Input, RichLog

    class UnifiedKernelApp(App[None]):
        TITLE = "Oathweaver Unified TUI"
        SUB_TITLE = "kernel command interface"
        BINDINGS = [
            Binding("ctrl+c", "quit", "Quit"),
            Binding("ctrl+l", "clear_log", "Clear"),
        ]

        CSS = """
        Screen {
          layout: vertical;
        }
        #body {
          height: 1fr;
        }
        #log {
          height: 1fr;
          border: round $accent;
        }
        #command-line {
          dock: bottom;
        }
        """

        def __init__(self, root: Path) -> None:
            super().__init__()
            self.router = TUICommandRouter(root)

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Vertical(id="body"):
                yield RichLog(id="log", highlight=True, markup=False, wrap=True)
                yield Input(placeholder="Type message or /command", id="command-line")
            yield Footer()

        def on_mount(self, event: Mount) -> None:
            _ = event
            log = self.query_one("#log", RichLog)
            log.write("Oathweaver Unified TUI")
            log.write("Type /help for commands.")

        @on(Input.Submitted, "#command-line")
        def on_submit(self, event: Input.Submitted) -> None:
            text = str(event.value or "").strip()
            event.input.value = ""
            if not text:
                return
            log = self.query_one("#log", RichLog)
            log.write(f"> {text}")
            out = self.router.dispatch(text)
            if out.text == "QUIT":
                self.exit()
                return
            if out.error:
                log.write(f"[error]{out.text}[/error]")
            else:
                log.write(out.text)

        def action_clear_log(self) -> None:
            log = self.query_one("#log", RichLog)
            log.clear()
            log.write("Log cleared.")

    UnifiedKernelApp(repo_root).run()


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    try:
        import textual  # noqa: F401
    except Exception:
        _run_plain_repl(repo_root)
        return
    _run_textual(repo_root)


if __name__ == "__main__":
    main()
