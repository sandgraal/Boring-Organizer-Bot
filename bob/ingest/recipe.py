"""Recipe document parser.

Supports structured recipe files in YAML or JSON format.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from bob.ingest.base import DocumentSection, ParsedDocument, Parser


class RecipeParser(Parser):
    """Parser for structured recipe files."""

    extensions = [".recipe.yaml", ".recipe.json"]

    def can_parse(self, path: Path) -> bool:
        """Check if this parser can handle the given file."""
        name = path.name.lower()
        return name.endswith(".recipe.yaml") or name.endswith(".recipe.json")

    def parse(self, path: Path) -> ParsedDocument:
        """Parse a recipe document into logical sections.

        Expected structure:
        ```yaml
        name: Recipe Name
        description: Short description
        prep_time: 30 minutes
        cook_time: 1 hour
        servings: 4
        ingredients:
          - item: flour
            amount: 2 cups
        instructions:
          - Step 1
          - Step 2
        notes: Optional notes
        ```
        """
        content = path.read_text(encoding="utf-8")

        if path.suffix.lower() == ".json" or path.name.endswith(".recipe.json"):
            data = json.loads(content)
        else:
            data = yaml.safe_load(content)

        sections: list[DocumentSection] = []

        # Title and description
        name = data.get("name", path.stem)
        description = data.get("description", "")

        if description:
            sections.append(
                DocumentSection(
                    content=f"# {name}\n\n{description}",
                    locator_type="section",
                    locator_value={"section": "description"},
                )
            )

        # Metadata
        metadata_parts = []
        for key in ["prep_time", "cook_time", "servings", "difficulty", "cuisine"]:
            if key in data:
                metadata_parts.append(f"{key.replace('_', ' ').title()}: {data[key]}")

        if metadata_parts:
            sections.append(
                DocumentSection(
                    content="\n".join(metadata_parts),
                    locator_type="section",
                    locator_value={"section": "metadata"},
                )
            )

        # Ingredients
        ingredients = data.get("ingredients", [])
        if ingredients:
            ing_lines = ["## Ingredients"]
            for ing in ingredients:
                if isinstance(ing, dict):
                    amount = ing.get("amount", "")
                    item = ing.get("item", "")
                    ing_lines.append(f"- {amount} {item}".strip())
                else:
                    ing_lines.append(f"- {ing}")

            sections.append(
                DocumentSection(
                    content="\n".join(ing_lines),
                    locator_type="section",
                    locator_value={"section": "ingredients"},
                )
            )

        # Instructions
        instructions = data.get("instructions", [])
        if instructions:
            inst_lines = ["## Instructions"]
            for i, step in enumerate(instructions, start=1):
                inst_lines.append(f"{i}. {step}")

            sections.append(
                DocumentSection(
                    content="\n".join(inst_lines),
                    locator_type="section",
                    locator_value={"section": "instructions"},
                )
            )

        # Notes
        notes = data.get("notes")
        if notes:
            sections.append(
                DocumentSection(
                    content=f"## Notes\n\n{notes}",
                    locator_type="section",
                    locator_value={"section": "notes"},
                )
            )

        return ParsedDocument(
            source_path=str(path),
            source_type="recipe",
            content=content,
            sections=sections,
            title=name,
            source_date=self.get_file_date(path),
            metadata=data,
        )
