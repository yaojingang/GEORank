import typer

app = typer.Typer()


@app.command()
def run(url: str):
    print(f"run diagnostic: {url}")
