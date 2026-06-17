import typer

from . import auth, company, diagnostic

app = typer.Typer(no_args_is_help=True)
app.add_typer(auth.app, name="auth")
app.add_typer(company.app, name="company")
app.add_typer(diagnostic.app, name="diagnostic")

if __name__ == "__main__":
  app()
