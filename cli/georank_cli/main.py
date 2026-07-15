import typer

from . import __version__
from . import auth, company, diagnostic

app = typer.Typer(no_args_is_help=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"georank-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the independently versioned CLI release.",
    ),
) -> None:
    """Operate a GEOrank deployment from the command line."""


app.add_typer(auth.app, name="auth")
app.add_typer(company.app, name="company")
app.add_typer(diagnostic.app, name="diagnostic")

if __name__ == "__main__":
    app()
