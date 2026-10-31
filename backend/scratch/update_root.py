import os

path = os.path.join("clinixai-health-flow", "src", "routes", "__root.tsx")
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace lovable import and usage
text = text.replace('import { reportLovableError } from "../lib/lovable-error-reporting";\n', '')
text = text.replace('import { reportLovableError } from "../lib/lovable-error-reporting";\r\n', '')
text = text.replace('reportLovableError(error, { boundary: "tanstack_root_error_component" });', '// Error recorded via console.error')

# Replace favicon
text = text.replace(
    '{ rel: "icon", href: "/favicon.ico", type: "image/x-icon" },',
    '{ rel: "icon", href: "/favicon.svg", type: "image/svg+xml" },\n      { rel: "alternate icon", href: "/favicon.ico", type: "image/x-icon" },'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("__root.tsx updated successfully.")

