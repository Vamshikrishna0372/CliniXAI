import os

path = os.path.join("clinixai-health-flow", "README.md")
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

lovable_block = """This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/e38911c6-98fe-4d26-9986-d94a61cb2074).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt."""

clinix_block = """## Architecture & Development

CliniXAI provides a modern, responsive web application for clinicians, administrators, hospital staff, and patients with integrated Explainable AI decision support."""

if lovable_block in text:
    text = text.replace(lovable_block, clinix_block)
    print("Replaced LF block in README.md")
elif lovable_block.replace("\n", "\r\n") in text:
    text = text.replace(lovable_block.replace("\n", "\r\n"), clinix_block.replace("\n", "\r\n"))
    print("Replaced CRLF block in README.md")
else:
    print("README block not matched exactly, replacing line by line...")
    lines = text.splitlines()
    clean_lines = [l for l in lines if "lovable" not in l.lower()]
    text = "\n".join(clean_lines)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Updated README.md successfully.")

