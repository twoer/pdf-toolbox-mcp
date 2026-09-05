---
name: Feature request
about: Suggest a new capability or improvement
title: "[feat] "
labels: enhancement
body:
  - type: textarea
    id: problem
    attributes:
      label: What do you want to do that isn't possible today?
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: How would you expect to ask the agent to do it?
      description: The natural-language phrasing matters — tools are designed around agent workflows.
  - type: dropdown
    id: fits
    attributes:
      label: Which area?
      options:
        - OCR / text extraction
        - Page surgery (split/merge/rotate)
        - Security (encrypt/redact/sanitize)
        - Inspection (fonts/images/repair)
        - Batch / performance
        - Distribution / docs
