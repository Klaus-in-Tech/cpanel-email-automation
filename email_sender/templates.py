from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path


def templates_dir() -> str:
    # templates directory at project root
    return str(Path(__file__).resolve().parents[1] / "templates")


def render_template(template_name: str, context: dict | None = None, templates_path: str | None = None) -> str:
    path = templates_path or templates_dir()
    env = Environment(
        loader=FileSystemLoader(path),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tmpl = env.get_template(template_name)
    return tmpl.render(context or {})
