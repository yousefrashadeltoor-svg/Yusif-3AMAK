# DAYFLOW native migration catalog

These JSON files are generated from the canonical DAYFLOW source definitions in the cleaned application archive:

- `themes.json`: 69 bilingual theme definitions, including the original palette, surface/material, shape, font, motion, texture and ornament tokens.
- `widgets.json`: 137 retained bilingual widget definitions, archetypes, categories, supported source size forms, styles and font choices. The 3 downloader-only widget records were intentionally removed with the downloader product.

## Important status

This directory stores source catalog data for the future Kotlin/Jetpack Compose port. It does **not** mean that native theme previews, all widget renderers, launcher pinning, or the entire Android UI have been implemented or tested. A catalog entry may be advertised as a native launcher widget only after its actual Android renderer and launcher behavior pass tests.

The original DAYFLOW screen/layout/interaction behavior remains the product reference. These files must not be used to replace the app with a reduced catalog-only UI.
