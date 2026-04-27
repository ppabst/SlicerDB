# SPDX-FileCopyrightText: 2026 LennyK
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared Jinja2Templates instance."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)
# Expose zip as both a filter (`a|zip(b)`) and a global (`zip(a,b)`) for templates.
templates.env.globals["zip"] = zip
templates.env.filters["zip"] = lambda a, b: list(zip(a, b, strict=False))
