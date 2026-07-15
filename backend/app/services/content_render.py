"""
Markdown 内容渲染服务
"""
from __future__ import annotations

from markdown import Markdown
from bs4 import BeautifulSoup


_BASE_EXTENSIONS = [
    "extra",
    "fenced_code",
    "tables",
    "sane_lists",
    "nl2br",
]


_DANGEROUS_TAGS = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "link",
    "meta",
    "base",
    "form",
    "input",
    "button",
    "textarea",
    "select",
}

_ALLOWED_TAGS = {
    "a",
    "abbr",
    "blockquote",
    "br",
    "code",
    "dd",
    "del",
    "details",
    "div",
    "dl",
    "dt",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "img",
    "ins",
    "kbd",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "sub",
    "summary",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

_GLOBAL_ATTRS = {"class", "id", "title", "aria-label", "aria-hidden"}
_TAG_ATTRS = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt", "width", "height", "loading"},
    "td": {"colspan", "rowspan", "align"},
    "th": {"colspan", "rowspan", "align", "scope"},
}


def _is_safe_url(raw_value: str, attr_name: str) -> bool:
    value = str(raw_value or "").strip()
    if not value:
        return False

    normalized = "".join(value.split()).lower()
    if normalized.startswith(("javascript:", "vbscript:", "data:text/html")):
        return False
    if normalized.startswith("data:"):
        return attr_name == "src" and normalized.startswith(
            (
                "data:image/png;",
                "data:image/jpeg;",
                "data:image/jpg;",
                "data:image/gif;",
                "data:image/webp;",
                "data:image/svg+xml;",
                "data:image/x-icon;",
                "data:image/vnd.microsoft.icon;",
            )
        )

    if "://" not in value and not value.lower().startswith(("mailto:", "tel:")):
        return True

    return value.lower().startswith(("http://", "https://", "mailto:", "tel:"))


def _sanitize_rendered_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")

    for node in list(soup.find_all(True)):
        tag_name = node.name.lower()
        if tag_name in _DANGEROUS_TAGS:
            node.decompose()
            continue
        if tag_name not in _ALLOWED_TAGS:
            node.unwrap()
            continue

        allowed_attrs = _GLOBAL_ATTRS | _TAG_ATTRS.get(tag_name, set())
        for attr_name, attr_value in list(node.attrs.items()):
            name = attr_name.lower()
            if name.startswith("on") or name in {"style", "srcdoc"} or name not in allowed_attrs:
                del node.attrs[attr_name]
                continue
            if name in {"href", "src"} and not _is_safe_url(
                attr_value[0] if isinstance(attr_value, list) else attr_value,
                name,
            ):
                del node.attrs[attr_name]

        if tag_name == "a" and node.get("href"):
            node["rel"] = "noopener noreferrer"

    return str(soup)


def render_markdown(markdown_body: str | None) -> str:
    """将 Markdown 渲染为 HTML，优先启用代码高亮。"""
    source = markdown_body or ""
    extensions = list(_BASE_EXTENSIONS)

    try:
        import pygments  # noqa: F401
    except Exception:
        pass
    else:
        extensions.append("codehilite")

    renderer = Markdown(extensions=extensions, output_format="html5")
    return _sanitize_rendered_html(renderer.convert(source))
