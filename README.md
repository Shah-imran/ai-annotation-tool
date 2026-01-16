# Annotation Tool (Scan Lab)

A modern, feature-rich image annotation tool built with PyQt5 for creating rectangular bounding box annotations with text descriptions and Q&A support. Designed for computer vision and machine learning workflows with YOLO format compatibility.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## ✨ Features

### Core Annotation Features
- 🖼️ **Flexible Image Loading**: Load from directories or file lists
- 📦 **Bounding Box Annotations**: Draw rectangular annotations with mouse
- 📝 **Text Descriptions**: Add detailed text descriptions to each annotation
- 🏷️ **Multi-Class Support**: Manage and assign multiple object classes
- 💾 **Auto-Save**: Automatic saving of annotations (configurable interval)
- 📁 **YOLO Format**: Native YOLO format support for ML workflows

### Q&A Annotation System
- ❓ **Question-Based Annotations**: Answer predefined questions for each bounding box
- 📋 **Customizable Questions**: Load questions from JSON files
- 💬 **Structured Answers**: Save Q&A data as JSON files per image
- 🔄 **Batch Q&A**: Efficient workflow for detailed annotation tasks

### User Experience
- 🎨 **Modern Dark Theme**: Easy on the eyes for long annotation sessions
- ⌨️ **Keyboard Shortcuts**: Efficient navigation and editing
- 📱 **Fully Resizable**: Adapts to any screen size and resolution
- 🔄 **Session Management**: Auto-restore last session on startup
- ⚙️ **Centralized Preferences**: Configure all settings in one place
- 📊 **Visual Feedback**: Real-time drawing with color-coded classes

### Advanced Features
- 🔍 **Image Magnification**: Zoom and inspect details
- 📋 **Annotation List**: Overview of all annotations in current image
- 🎯 **Smart Selection**: Click to select and edit annotations
- 📂 **Recent Files**: Quick access to recently used files
- 🔧 **Customizable Settings**: Load settings from custom file paths

## 🚀 Quick Start

### Installation

#### Option 1: Using pipenv (Recommended)
```bash
# Install pipenv if not already installed
pip install pipenv

# Install dependencies
pipenv install

# Activate virtual environment
pipenv shell
```

#### Option 2: Using pip
```bash
pip install -r requirements.txt
```

### Running the Application

#### Basic Launch
```bash
python main_annotation_tool.py
```

#### With Command Line Arguments
```bash
# Load images from directory
python main_annotation_tool.py --images /path/to/images

# Load images from file list
python main_annotation_tool.py --list /path/to/train.txt --base-dir /path/to/base

# Load with classes
python main_annotation_tool.py --images /path/to/images --classes /path/to/classes.txt

# Load sample data for testing
python main_annotation_tool.py --sample-data
```

#### As Python Module
```bash
python -m annotation_tool.main --images /path/to/images
```

## 📖 Usage Guide

### Basic Workflow

1. **Load Images**: Use `File > Load Images from Directory` or `File > Load Images from List`
2. **Load Classes**: Use `File > Load Classes` to load your class names file
3. **Draw Annotations**: 
   - Select a class from the dropdown or press `0-9` keys
   - Click and drag on the image to draw a bounding box
   - Add text description in the control panel
4. **Navigate**: Use `A`/`D` keys or navigation buttons to move between images
5. **Save**: Annotations auto-save, or press `Ctrl+S` to save manually

### Q&A Workflow

1. **Enable Q&A Mode**: Go to `Tools > Enable Q&A Annotations`
2. **Configure Questions**: Go to `Tools > Preferences > Q&A Settings`
   - Browse for a questions JSON file or create a sample
   - Set the answers save folder
3. **Annotate**: Draw bounding boxes as usual
4. **Answer Questions**: For each selected annotation, answer the questions in the Q&A panel
5. **Auto-Save**: Q&A answers are automatically saved to JSON files

### Preferences

Access all settings via `Tools > Preferences`:

- **File Paths Tab**: Configure default image directories, list files, and classes files
- **Q&A Settings Tab**: Configure questions files and answers folder
- **General Tab**: 
  - Settings file location
  - Auto-load last session
  - Auto-save interval
  - Maximum recent items

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `A` | Previous image |
| `D` | Next image |
| `0-9` | Select class (0-9) |
| `R` | Delete selected annotation |
| `C` | Clear all annotations |
| `Ctrl+S` | Save annotations |
| `Ctrl+O` | Open images |
| `I` | Toggle image magnification |
| `M` | Cycle magnification method |
| `ESC` | Exit application |

### Mouse Controls

| Action | Function |
|--------|----------|
| **Left Click + Drag** | Draw new bounding box |
| **Right Click** | Select existing annotation |
| **Right Drag** | Move selected annotation |
| **Mouse Wheel** | Zoom in/out (when magnification enabled) |

## 📄 File Formats

### Class Names File (`.txt` or `.names`)

One class name per line:
```
person
car
bicycle
motorcycle
airplane
```

### Image List File (`.txt`)

One image path per line (absolute or relative):
```
/path/to/image1.jpg
/path/to/image2.jpg
relative/path/image3.jpg
```

### Annotation Format (YOLO - `.txt`)

Saved alongside images with same filename:
```
class_id center_x center_y width height description_text
0 0.5 0.5 0.3 0.4 person walking
1 0.8 0.2 0.1 0.15 red car
```

Coordinates are normalized (0.0 to 1.0).

### Questions File (JSON)

For Q&A annotations:
```json
{
  "questions": [
    "What is the primary object in this bounding box?",
    "Is there any damage or defect visible?",
    "What is the overall condition?"
  ]
}
```

### Q&A Answers File (JSON)

Saved as `[image_name].qa.json`:
```json
{
  "image": "image001.jpg",
  "annotations": [
    {
      "index": 0,
      "class_id": 0,
      "bbox": {"x": 100, "y": 150, "width": 200, "height": 300},
      "answers": {
        "What is the primary object in this bounding box?": "Person",
        "Is there any damage or defect visible?": "No",
        "What is the overall condition?": "Good"
      }
    }
  ]
}
```

## 🏗️ Architecture

The application follows **MVC (Model-View-Controller)** architecture for maintainability and extensibility:

```
annotation_tool/
├── models/              # Data layer
│   ├── bounding_box.py         # BoundingBox data class
│   ├── annotation_model.py     # Annotation management
│   ├── image_model.py          # Image loading and navigation
│   ├── settings_model.py       # Application settings
│   ├── questions_model.py      # Q&A questions management
│   └── qa_answers_model.py     # Q&A answers management
├── views/              # UI layer
│   ├── main_window.py          # Main application window
│   ├── image_canvas.py          # Image display and drawing
│   ├── control_panel.py        # Control panel UI
│   └── preferences_dialog.py   # Settings dialog
├── controllers/        # Business logic layer
│   ├── annotation_controller.py  # Annotation operations
│   └── main_controller.py         # Main application logic
└── main.py            # Application entry point
```

### Key Design Principles

- **Separation of Concerns**: Models handle data, Views handle UI, Controllers handle logic
- **Signal-Slot Architecture**: Loose coupling via PyQt5 signals
- **Extensibility**: Easy to add new annotation types or features
- **Resizable UI**: All windows and dialogs adapt to screen size

## 🔨 Building Executable

The application can be bundled as a standalone executable using PyInstaller:

```bash
# Build executable
pyinstaller annotation_tool.spec

# Executable will be in dist/Annotation Tool.exe
```

### Settings File Location

- **Development**: `settings/settings.json` in project root
- **Bundled EXE**: User's AppData directory (Windows)
  - `C:\Users\<Username>\AppData\Roaming\Scan Lab\Annotation Tool (Scan Lab)\settings.json`

You can also load settings from a custom file via `File > Load Settings File...`

## 📦 Dependencies

### Core Dependencies
- **PyQt5** >= 5.15.0 - GUI framework
- **opencv-python** >= 4.5.0 - Image processing
- **numpy** >= 1.20.0 - Numerical computing

### Optional Dependencies
- **pyinstaller** - For building executables
- **pandas**, **openpyxl** - For data export (if needed)
- **matplotlib**, **seaborn** - For visualizations (if needed)

See `requirements.txt` or `Pipfile` for complete list.

## 🎯 Use Cases

- **Computer Vision Projects**: Prepare training data for object detection models
- **YOLO Training**: Create annotations compatible with YOLO format
- **Data Labeling**: Efficient annotation workflow for ML datasets
- **Quality Control**: Q&A system for detailed annotation validation
- **Batch Processing**: Process large image datasets with session management

## 🔧 Troubleshooting

### Common Issues

**Images not loading**
- Check file permissions
- Verify image format is supported (JPEG, PNG, BMP, TIFF)
- Ensure paths are correct (use absolute paths if relative paths fail)

**Annotations not saving**
- Check write permissions in image directory
- Verify disk space available
- Check if file is locked by another process

**PyQt5 not found**
```bash
pip install PyQt5
```

**Application won't start**
- Ensure Python 3.10+ is installed
- Check all dependencies are installed: `pip install -r requirements.txt`
- Verify virtual environment is activated (if using)

**Settings not persisting**
- Check write permissions for settings directory
- Verify settings file path in Preferences > General tab
- Try loading settings from a custom file

### Supported Image Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)
- TIFF (.tiff, .tif)

## 🚧 Extending the Application

The MVC architecture makes it easy to extend:

### Adding New Annotation Types
1. Extend `BoundingBox` model or create new annotation models
2. Update `ImageCanvas` view to handle new drawing modes
3. Add corresponding controllers for new annotation types

### Custom File Formats
1. Extend `AnnotationModel` to support new formats
2. Add import/export methods in controllers
3. Update UI to provide new format options

### Additional Features Ideas
- Copy/Paste annotations between images
- Undo/Redo functionality
- Batch operations
- Export to other formats (COCO, Pascal VOC)
- Annotation statistics and analytics

## 📝 License

This project is open source and available under the MIT License.

## 👥 Contributing

Contributions are welcome! The modular architecture makes it easy to contribute:

1. Fork the repository
2. Create a feature branch
3. Follow the MVC pattern
4. Add tests for new functionality
5. Submit a pull request

## 📞 Support

For issues, questions, or contributions, please open an issue on the repository.

---

**Built with ❤️ for Scan Lab**
