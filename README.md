# refua-notebook

Jupyter UI extensions for drug discovery visualization. This package provides inline notebook widgets for displaying ADMET properties, 3D molecular structures, and SMILES drawings from Refua objects. It also includes an IPython extension that automatically registers rich HTML representations for Refua objects.

## Features

- **IPython Extension**: Automatic widget display for Refua `SM`, `Protein`, `Complex`, and `FoldResult` objects
- **Rich Visualization**: 2D structures, 3D Mol* views, and property summaries rendered directly from Refua objects

## Installation

```bash
pip install refua-notebook
```

Or with Poetry:

```bash
poetry add refua-notebook
```

`refua-notebook` depends on Refua directly, so installing this package will also
install `refua`.

## Quick Start

### Automatic Widget Display (IPython Extension)

The easiest way to use refua-notebook is to load it as an IPython extension. This automatically registers rich HTML representations for Refua objects:

```python
# Option 1: Load as IPython extension
%load_ext refua_notebook

# Option 2: Activate programmatically
import refua_notebook
refua_notebook.activate()

# Now Refua objects display automatically as widgets!
from refua import SM, Protein, Complex

# Proteins show sequence info (and 3D structure if folded)
Protein("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ", ids="A")

# Folded complexes show a tabbed view with 3D structure, affinity, and molecule details
complex = Complex([
    Protein("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ", ids="A"),
    SM("CCO"),
]).request_affinity()
result = complex.fold()
complex  # Shows 3D structure with binding affinity (uses complex.last_fold)
```
Displaying the Refua objects directly is enough; the extension handles rich
HTML rendering automatically.

### JupyterLab Renderer (Required for JupyterLab)

JupyterLab blocks inline scripts, so the package ships a prebuilt JupyterLab
renderer that loads Mol* and SmilesDrawer locally and renders the
`application/vnd.refua+json` MIME output. With recent JupyterLab versions, no
`jupyter labextension install` or `jupyter lab build` step is required—installing
the Python package is enough.

To rebuild the prebuilt labextension (requires network access for npm packages):

```bash
cd labextension
yarn install
yarn build:prod
```

## Refua Integration

`refua-notebook` is built on top of the [Refua](https://github.com/tensorspace-ai/refua)
drug discovery toolkit:

```python
from refua import Complex, Protein, SM

# Fold a protein-ligand complex
complex = Complex([
    Protein("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ", ids="A"),
    SM("CCO"),
]).request_affinity()
result = complex.fold()

# Display the Refua objects directly
complex
result.affinity
```

## Examples

The `examples/` directory includes runnable notebooks:

- `refua_folding.ipynb`
- `refua_antibody_design.ipynb`

Rebuild all examples (executes and writes outputs in-place):

```bash
poetry run jupyter nbconvert --execute --to notebook --inplace examples/*.ipynb
```

## API Reference

### Extension Functions

```python
# Load extension (in notebook)
%load_ext refua_notebook

# Programmatic activation
import refua_notebook
refua_notebook.activate()     # Enable automatic widget display
refua_notebook.deactivate()   # Disable automatic widget display
refua_notebook.is_active()    # Check if extension is active
```

## Development

```bash
# Clone the repository
git clone <your-repo-url>
cd refua-notebook

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Optional browser-level JupyterLab widget test
poetry run playwright install chromium
REFUA_JLAB_PLAYWRIGHT=1 poetry run pytest tests/test_jupyterlab_playwright.py

# Format code
poetry run black refua_notebook tests
```

## License

MIT License
