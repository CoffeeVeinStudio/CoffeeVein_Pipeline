# CoffeeVein Studio Pipeline - AGENTS.md

This file contains guidelines and commands for agentic coding agents working in this repository.

## Repository Overview

This is a VFX/post-production pipeline for CoffeeVein Studio, primarily focused on Nuke but designed for cross-DCC expansion. The pipeline includes custom tools, gizmos, scripts, and TikManager integration for asset/shot management.

## Build/Lint/Test Commands

### Python Code Quality
```bash
# Lint Python files (if available)
python -m flake8 nuke/ --max-line-length=120 --ignore=E203,W503

# Type checking (if available)
python -m mypy nuke/ --ignore-missing-imports

# Run specific test (TikManager has test structure)
cd tikmanager/tik_manager4
python -m pytest tests/test_core.py -v
```

### Nuke Development
```bash
# Test Nuke scripts in headless mode (if supported)
nuke -t nuke/internal/ScriptSetup/scriptSetup.py

# Validate Nuke scripts syntax
python -c "import ast; ast.parse(open('nuke/init.py').read())"
```

## Code Style Guidelines

### Import Organization
- Standard library imports first
- Third-party imports second (nuke, nukescripts, PySide2)
- Local imports third
- Use `from __future__ import annotations` for type hints in Python 3.7+

```python
# Standard library
import os
import json
from pathlib import Path
from typing import List, Optional, Tuple

# Third-party
import nuke
import nukescripts
from PySide2.QtCore import Qt, QPointF
from PySide2.QtWidgets import QGraphicsView, QMessageBox

# Local imports
from image_display import ImageDisplay
from dialog import EXRImportDialog
```

### Naming Conventions
- **Classes**: PascalCase (`CoffeeBoard`, `ImageDisplay`, `EXRImportDialog`)
- **Functions/Methods**: snake_case (`add_image`, `paste_from_clipboard`, `_layout_images`)
- **Variables**: snake_case (`scale_factor`, `pan_origin`, `image_items`)
- **Constants**: UPPER_SNAKE_CASE (`MIN_SCALE`, `MAX_SCALE`, `COLUMNS`)
- **Private methods**: Prefix with underscore (`_prompt_for_layer`, `_layout_images`)

### Type Hints
- Use type hints for all function signatures and class attributes
- Use `Optional[T]` for nullable values
- Use `List[T]`, `Dict[K, V]` for collections
- Import from `typing` module

```python
def add_image(self, path: str, layer: str = 'rgba', preview_format: str = 'jpg') -> None:
    """Adds a new ImageDisplay item to the board."""
    
image_items: List['ImageDisplay']
current_save_path: Optional[str]
```

### Documentation
- Use comprehensive docstrings for all classes and public methods
- Follow Google/NumPy style docstring format
- Include Args, Returns, Raises sections where applicable
- Use inline comments sparingly for complex logic

```python
def wheelEvent(self, event: QWheelEvent) -> None:
    """Handles zooming in and out of the view using the mouse wheel.
    
    The zoom is centered around the mouse cursor's current position.
    
    Args:
        event (QWheelEvent): The event object containing the wheel movement data.
    """
```

### Error Handling
- Use specific exception types
- Include meaningful error messages
- Use try/except blocks for external operations
- Log errors with print statements for Nuke integration

```python
try:
    image_item = ImageDisplay(path, layer, preview_format)
    self.scene.addItem(image_item)
    self.image_items.append(image_item)
except Exception as e:
    print(f"Failed to add image {path}: {e}")
    raise
```

### File Structure
- **Nuke Tools**: `nuke/internal/` for custom tools, `nuke/3rd_party/` for external plugins
- **Gizmos**: Separate folders with descriptive names
- **Scripts**: Organize by functionality (ScriptSetup, CoffeeBoard)
- **Settings**: JSON configuration files in `tikmanager/coffeevein_settings/`

### Nuke-Specific Guidelines
- Use `nuke.pluginAddPath()` for plugin registration
- Use `nukescripts.panels.registerWidgetAsPanel()` for custom panels
- Handle Nuke progress tasks for long operations
- Use `nuke.message()` and `nuke.warning()` for user feedback
- Store node positions using `xpos` and `ypos` knobs

### Qt/PySide2 Guidelines
- Use PySide2 for Qt integration
- Follow Qt signal/slot patterns
- Use proper parent-child relationships for memory management
- Handle events by overriding appropriate methods

```python
class CoffeeBoard(QGraphicsView):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
    def wheelEvent(self, event: QWheelEvent) -> None:
        # Custom zoom implementation
```

### Path Handling
- Use `pathlib.Path` for cross-platform path operations
- Use `os.path.join()` for legacy code
- Handle relative vs absolute paths appropriately
- Validate file existence before operations

### Constants and Configuration
- Define class-level constants for magic numbers
- Use JSON files for user-configurable settings
- Separate hardcoded values from logic

```python
class CoffeeBoard(QGraphicsView):
    min_scale: float = 0.001
    max_scale: float = 100.0
    columns: int = 4
    preview_format: str = 'jpg'
```

## Testing Strategy

### Unit Tests
- Test core functionality in isolation
- Mock Nuke dependencies where possible
- Focus on data processing and business logic

### Integration Tests
- Test Nuke plugin loading
- Verify menu registration
- Test file I/O operations

### Manual Testing
- Test in Nuke environment for UI components
- Verify drag-and-drop functionality
- Test with actual image files and EXR sequences

## Development Workflow

1. **Feature Development**: Create in appropriate directory (`nuke/internal/` for custom tools)
2. **Testing**: Test in Nuke environment, verify plugin loading
3. **Documentation**: Update docstrings and comments
4. **Integration**: Add to `init.py` and `menu.py` if needed
5. **Validation**: Test pipeline loading and functionality

## Pipeline Integration

### Plugin Registration
- Internal tools automatically loaded via `nuke/init.py`
- Menu items registered in `nuke/menu.py`
- Use proper plugin path structure

### TikManager Integration
- Settings stored in `tikmanager/coffeevein_settings/`
- Follow TikManager conventions for project structure
- Use TikManager API for version control and publishing

### Cross-DCC Considerations
- Shared resources in `shared/` directory
- Avoid Nuke-specific code in shared modules
- Use abstraction layers for DCC-specific functionality