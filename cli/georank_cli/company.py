import typer

app = typer.Typer()


@app.command()
def submit(url: str):
    print(f"submit company: {url}")
