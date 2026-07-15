import typer

app = typer.Typer()


@app.command()
def login():
    print("auth login")
