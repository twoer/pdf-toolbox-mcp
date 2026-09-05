---
name: Bug report
about: Something didn't work as expected
title: "[bug] "
labels: bug
body:
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: Also include what you expected instead.
    validations:
      required: true
  - type: textarea
    id: probe
    attributes:
      label: Dependency probe output
      description: Output of `uv run pdftoolbox probe all` (or the `dependency_status` tool result)
    validations:
      required: true
  - type: textarea
    id: error
    attributes:
      label: Structured error JSON
      description: The `{"ok": false, "error": ...}` payload if any
  - type: dropdown
    id: os
    attributes:
      label: OS
      options: [macOS, Linux, Windows]
    validations:
      required: true
  - type: textarea
    id: client
    attributes:
      label: MCP client / version
      description: e.g. Claude Desktop 1.x, Claude Code 2.x, Cursor …
