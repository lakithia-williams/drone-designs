"""Puts show.json into the preview page.

Writes the GitHub Pages copy to <repo>/docs/<PAGES_FOLDER>/index.html, so every role's show
gets its own link: https://<username>.github.io/drone-designs/<PAGES_FOLDER>/
Also writes preview/artifact.html (a body-only copy, not committed).
"""
import os
PAGES_FOLDER = "ford-racing"
here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "preview", "template.html")).read()
data = open(os.path.join(here, "output", "show.json")).read()
page = tpl.replace("/*SHOW_JSON*/null", data)
open(os.path.join(here, "preview", "artifact.html"), "w").write(page)
head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')
title_end = page.index("</style>") + len("</style>")
full = head + page[:title_end] + "\n</head>\n<body>\n" + page[title_end:] + "\n</body>\n</html>\n"
out = os.path.join(here, "..", "docs", PAGES_FOLDER)
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "index.html"), "w").write(full)
print("ok", os.path.normpath(os.path.join(out, "index.html")))
