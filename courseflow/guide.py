"""Local help shared by the desktop, Harness sidebar, and slash command."""
from pathlib import Path


def _assistant_help(intro, examples):
    notes = []
    for line in intro.splitlines():
        if line.startswith("- **"):
            title, _, text = line[4:].partition("**")
            notes.append({"title": title, "text": text.strip()})
    hint, *blocks = examples.split("\n#### ")
    items = []
    for block in blocks:
        title, _, body = block.partition("\n")
        lines = body.strip().splitlines()
        items.append({"title": title, "hint": "\n".join(line for line in lines if not line.startswith("> ")).strip(),
                      "text": "\n".join(line[2:] for line in lines if line.startswith("> "))})
    return {"notes": notes, "hint": hint.strip(), "examples": items}


def usage_guide(*, commands=True, examples=True):
    title, *parts = (Path(__file__).parent / "data" / "assistant-guide.md").read_text(encoding="utf-8").split("\n## ")
    sections = []
    for part in parts:
        heading, body = part.split("\n", 1)
        if not commands and heading == "命令":
            continue
        section = {"title": heading, "body": body.strip()}
        if heading == "助手如何使用":
            intro, _, example_body = body.partition("\n### 参考例句\n")
            if examples:
                section["layout"] = _assistant_help(intro, example_body)
            else:
                section["body"] = intro.strip()
        sections.append(section)
    return {"type": "command_help", "sections": sections, "message": "\n\n".join(
        [title.strip(), *(f"## {section['title']}\n\n{section['body']}" for section in sections)]),
        "sample": "帮我按这张图生成课表"}
