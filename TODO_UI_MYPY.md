# TODO: Stricter mypy for `ui/`

`ui/` is currently excluded from mypy errors via `[[tool.mypy.overrides]]` in `pyproject.toml` (`module = "ui.*"`, `ignore_errors = true`). Discord UI views use dynamic callback wiring and interaction payload shapes that do not match stubs well.

## Later

- [ ] Remove or narrow the `ui.*` mypy override in `pyproject.toml`.
- [ ] Fix reported issues in `ui/*.py` (e.g. `interaction.data` / `custom_id`, assigning async handlers to `discord.ui` callbacks, optional `Message` / ids) using `cast`, guards, or small refactors.
- [ ] Run `uv run mypy cogs` (and full `make lint`) until clean without the override.
