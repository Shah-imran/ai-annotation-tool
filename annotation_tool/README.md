# Annotation Tool (Scan Lab)

A modern image annotation tool built using MVC (Model-View-Controller) architecture. This tool is designed for creating rectangular bounding box annotations with text descriptions in YOLO format.

## Features

- 🖼️ **Image Support**: Load images from directories or file lists
- 📦 **Rectangular Annotations**: Draw bounding boxes with mouse
- 📝 **Text Descriptions**: Add detailed text descriptions to annotations
- 🏷️ **Class Management**: Support for multiple object classes
- ⌨️ **Keyboard Shortcuts**: Efficient navigation and editing
- 💾 **Auto-save**: Automatic saving of annotations
- 🎨 **Dark Theme**: Modern dark UI theme
- 📁 **YOLO Format**: Compatible with YOLO annotation format

## Architecture

The application follows MVC architecture for maintainability and extensibility:

```
annotation_tool/
├── models/           # Data models
│   ├── bounding_box.py      # BoundingBox data class
│   ├── annotation_model.py  # Annotation management
│   └── image_model.py       # Image loading and navigation
├── views/            # UI components
│   ├── main_window.py       # Main application window
│   ├── image_canvas.py      # Image display and drawing
│   └── control_panel.py     # Control panel UI
├── controllers/      # Business logic
│   ├── annotation_controller.py  # Annotation operations
│   └── main_controller.py        # Main application logic
└── main.py          # Application entry point
```

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. The main dependencies are:

- PyQt5 >= 5.15.0 (GUI framework)
- opencv-python >= 4.5.0 (Image processing)
- numpy >= 1.20.0 (Numerical computing)

## Usage

### Running the Application

There are several ways to run the annotation tool:

#### 1. Basic Launch

```bash
python main_annotation_tool.py
```

#### 2. With Command Line Arguments

```bash
# Load images from directory
python main_annotation_tool.py --images /path/to/images

# Load images from file list
python main_annotation_tool.py --list /path/to/train.txt

# Load with classes
python main_annotation_tool.py --images /path/to/images --classes /path/to/classes.txt

# Load sample data for testing
python main_annotation_tool.py --sample-data
```

#### 3. As Python Module

```bash
python -m annotation_tool.main --images /path/to/images
```

### Keyboard Shortcuts

| Key      | Action                     |
| -------- | -------------------------- |
| `A`      | Previous image             |
| `D`      | Next image                 |
| `0-9`    | Select class (0-9)         |
| `R`      | Delete selected annotation |
| `C`      | Clear all annotations      |
| `Ctrl+S` | Save annotations           |
| `Ctrl+O` | Open images                |
| `ESC`    | Exit application           |

### Mouse Controls

| Action                | Function                   |
| --------------------- | -------------------------- |
| **Left Click + Drag** | Draw new bounding box      |
| **Right Click**       | Select existing annotation |
| **Right Drag**        | Move selected annotation   |

## File Formats

### Class Names File

Create a text file with one class name per line:

```
person
car
bicycle
motorcycle
airplane
```

### Image List File (train.txt style)

Create a text file with one image path per line:

```
/path/to/image1.jpg
/path/to/image2.jpg
relative/path/image3.jpg
```

### Annotation Format (YOLO)

Annotations are saved as `.txt` files with the same name as the image:

```
class_id center_x center_y width height description text
0 0.5 0.5 0.3 0.4 person walking
1 0.8 0.2 0.1 0.15 red car
```

## Features in Detail

### Image Canvas

- **Zoom and Pan**: Automatic image scaling to fit canvas
- **Visual Feedback**: Real-time drawing of bounding boxes
- **Color Coding**: Different colors for different classes
- **Selection Highlighting**: Selected annotations shown in white

### Control Panel

- **Navigation**: Image counter and navigation buttons
- **Class Selection**: Dropdown for selecting current class
- **Annotation Details**: View and edit selected annotation
- **Text Input**: Multi-line text description support
- **Annotation List**: Overview of all annotations in current image

### Auto-save

- Annotations are automatically saved when:
  - New annotation is drawn
  - Existing annotation is moved
  - Annotation text is modified
  - Annotation is deleted

## Extending the Application

The MVC architecture makes it easy to extend the application:

### Adding New Annotation Types

1. Extend the `BoundingBox` model or create new annotation models
2. Update the `ImageCanvas` view to handle new drawing modes
3. Add corresponding controllers for new annotation types

### Custom File Formats

1. Extend the `AnnotationModel` to support new formats
2. Add import/export methods in the controllers
3. Update the UI to provide new format options

### Additional Features

- **Copy/Paste**: Already supported via Ctrl+C (copy to subsequent images)
- **Undo/Redo**: Can be added to the annotation controller
- **Batch Operations**: Can be added to the main controller
- **Data Export**: JSON export already implemented

## Troubleshooting

### Common Issues

1. **Images not loading**: Check file permissions and supported formats
2. **Annotations not saving**: Ensure write permissions in image directory
3. **PyQt5 not found**: Install with `pip install PyQt5`
4. **Dark theme issues**: Update PyQt5 to latest version

### Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)
- TIFF (.tiff, .tif)

## Contributing

The modular architecture makes contributions welcome:

1. Fork the repository
2. Create a feature branch
3. Follow the MVC pattern
4. Add tests for new functionality
5. Submit a pull request

## License

This project is open source and available under the MIT License.
