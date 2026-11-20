# CI and brand

## What CI checks

`.github/workflows/ci.yml` runs on every push and pull request. It needs no age key and no repository secret, and decrypts nothing. It runs the same tasks you run locally:

| Check | Same as running locally |
|---|---|
| Manifest: `servers.yaml` matches its schema | `task manifest:check` |
| Installer tests | `task test` |
| Secrets store is encrypted, no plaintext file | `task sops:validate` |
| Compose file is valid | `task docker:config` |
| No leaked secret in the git history | gitleaks, over the full history |

A red check on a pull request must be fixed before merge. See [What CI checks](operator-guide.md#what-ci-checks) in the operator guide.

Two more workflows run beside it:

- `brand.yml` runs `task brand:check` on pull requests that touch `brand/` or the generator, and on pushes to `main`.
- `docs-pages.yml` builds and checks this site on pull requests and on `main`, and deploys it to GitHub Pages only from `main`.

## Documentation site

This site is built with [Zensical](https://zensical.org/) from `website/` and `zensical.toml`. The operator guide is not copied: the site includes `docs/operator-guide.md`, so editing the guide changes the site with no other edit.

| Task | Effect |
|---|---|
| `task docs:build` | Copy the brand assets, then run `zensical build --strict` into `site/`. |
| `task docs:check` | Build, then run `scripts/check_docs.py` on `site/`: links and anchors, `lang`, title, one `h1`, alt text, the base path, palette contrast and an absolute `og:image`. |
| `task docs:serve` | Serve the site locally with live reload. |

## Brand

The logo, README banner, favicon and social preview live in `brand/`:

- `brand/data/` holds the palette and the verified facts.
- `brand/src/` holds the SVG templates.
- `brand/generated/` holds the committed output, which is never edited by hand.

`task brand:generate` renders the output; the PNG needs `rsvg-convert`. `task brand:check` fails when the output is stale. The site copies the banner, the favicon and the social preview from `brand/generated/` at build time, so there is one source for each.

The palette is Catppuccin Macchiato with a lavender accent (`#b7bdf8`).
