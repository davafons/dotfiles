---
name: xlsx-to-html
description: Convert Excel files (.xlsx/.xls) to standalone HTML with search and filter. Use when the user wants to convert Excel/spreadsheet files to HTML, view Excel on the web, or make spreadsheets AI-readable.
---

# Excel to HTML Converter

Convert Excel files to standalone HTML that preserves the visual structure with search/filter/sort capabilities.

## Requirements

```bash
pip install openpyxl
```

## Usage

```bash
python ~/dotfiles/skills/xlsx-to-html/xlsx_to_web.py input.xlsx
python ~/dotfiles/skills/xlsx-to-html/xlsx_to_web.py input.xlsx --output-dir ./docs
python ~/dotfiles/skills/xlsx-to-html/xlsx_to_web.py ./folder_with_excels/
```

## Output Features

- Preserves table structure from Excel
- Multi-sheet support with tabs
- Real-time search with highlighting
- Click column headers to sort
- Responsive design
- Single standalone HTML file (no server needed)
