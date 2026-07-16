"""前台菜单栏配置的默认值与输入规范化。"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit


NAVIGATION_MENU_SETTING_KEY = "navigation_menu"
MAX_NAVIGATION_ITEMS = 12
DEFAULT_NAVIGATION_MENU = {
    "items": [
        {"id": "companies", "label": "公司", "url": "/companies", "target": "_blank", "enabled": True},
        {"id": "diagnostic", "label": "诊断", "url": "/diagnostic", "target": "_blank", "enabled": True},
        {"id": "solutions", "label": "问答", "url": "/solutions", "target": "_blank", "enabled": True},
        {"id": "plans", "label": "方案", "url": "/plans", "target": "_blank", "enabled": True},
        {"id": "keywords", "label": "拓词", "url": "/keywords", "target": "_blank", "enabled": True},
        {"id": "tools", "label": "工具", "url": "/tools", "target": "_blank", "enabled": True},
        {"id": "experts", "label": "专家", "url": "/experts", "target": "_blank", "enabled": True},
        {"id": "tutorial", "label": "教程", "url": "/tutorial", "target": "_blank", "enabled": True},
        {
            "id": "github",
            "label": "GitHub",
            "url": "https://github.com/yaojingang/GEORank",
            "target": "_blank",
            "enabled": True,
        },
    ]
}


class NavigationMenuValidationError(ValueError):
    """菜单栏配置不满足公开渲染约束。"""


def get_default_navigation_menu() -> dict[str, list[dict[str, Any]]]:
    return deepcopy(DEFAULT_NAVIGATION_MENU)


def _normalize_navigation_url(value: Any, index: int) -> str:
    url = str(value or "").strip()
    if not url:
        raise NavigationMenuValidationError(f"第 {index} 个菜单项缺少 URL")
    if len(url) > 2048:
        raise NavigationMenuValidationError(f"第 {index} 个菜单项 URL 不能超过 2048 个字符")
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        raise NavigationMenuValidationError(f"第 {index} 个菜单项 URL 包含不可见字符")
    if url.startswith("/") and not url.startswith("//"):
        return url
    if url.startswith("#") and len(url) > 1:
        return url
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise NavigationMenuValidationError(f"第 {index} 个菜单项 URL 无效") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise NavigationMenuValidationError(
            f"第 {index} 个菜单项 URL 仅支持站内路径、锚点或 HTTP/HTTPS 地址"
        )
    return url


def normalize_navigation_menu_payload(payload: Any) -> dict[str, list[dict[str, Any]]]:
    if payload is None:
        return get_default_navigation_menu()
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise NavigationMenuValidationError("菜单栏配置必须包含 items 数组")

    raw_items = payload["items"]
    if not raw_items:
        raise NavigationMenuValidationError("菜单栏至少需要保留一个菜单项")
    if len(raw_items) > MAX_NAVIGATION_ITEMS:
        raise NavigationMenuValidationError(f"菜单栏最多支持 {MAX_NAVIGATION_ITEMS} 个菜单项")

    normalized_items: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for position, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            raise NavigationMenuValidationError(f"第 {position} 个菜单项格式无效")
        label = str(raw_item.get("label") or "").strip()
        if not label:
            raise NavigationMenuValidationError(f"第 {position} 个菜单项缺少文案")
        if len(label) > 40:
            raise NavigationMenuValidationError(f"第 {position} 个菜单项文案不能超过 40 个字符")

        raw_id = str(raw_item.get("id") or f"menu-{position}").strip()
        item_id = raw_id if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", raw_id) else f"menu-{position}"
        if item_id in used_ids:
            item_id = f"{item_id}-{position}"
        used_ids.add(item_id)

        target_value = str(raw_item.get("target") or "_blank").strip().lower()
        target = "_self" if target_value in {"_self", "same_tab"} else "_blank"
        normalized_items.append(
            {
                "id": item_id,
                "label": label,
                "url": _normalize_navigation_url(raw_item.get("url"), position),
                "target": target,
                "enabled": raw_item.get("enabled") is not False,
            }
        )

    if not any(item["enabled"] for item in normalized_items):
        raise NavigationMenuValidationError("菜单栏至少需要保留一个菜单项显示")
    return {"items": normalized_items}
