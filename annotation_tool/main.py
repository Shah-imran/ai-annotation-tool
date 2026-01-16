"""
Main entry point for the Annotation Tool (Scan Lab).
"""
import sys
import os
import argparse
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from .controllers import MainController


def setup_application():
    """Setup and configure the QApplication."""
    # Enable high DPI scaling before creating QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Annotation Tool (Scan Lab)")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Scan Lab")
    
    return app


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Annotation Tool (Scan Lab) - Image Annotation Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m annotation_tool.main
  python -m annotation_tool.main --images /path/to/images
  python -m annotation_tool.main --images /path/to/images --classes /path/to/classes.txt
  python -m annotation_tool.main --list /path/to/train.txt --classes /path/to/classes.txt
        """
    )
    
    parser.add_argument(
        '--images', 
        type=str, 
        help='Directory containing images to annotate'
    )
    
    parser.add_argument(
        '--list', 
        type=str, 
        help='Text file containing list of image paths'
    )
    
    parser.add_argument(
        '--classes', 
        type=str, 
        help='Text file containing class names (one per line)'
    )
    
    parser.add_argument(
        '--base-dir',
        type=str,
        default='',
        help='Base directory for relative paths in image list file'
    )
    
    parser.add_argument(
        '--sample-data',
        action='store_true',
        help='Load sample data for testing'
    )
    
    return parser.parse_args()


def main():
    """Main application entry point."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Setup application
    app = setup_application()
    
    # Create main controller
    controller = MainController()
    
    # Load data based on arguments (overrides last session)
    if args.sample_data:
        controller.load_sample_data()
    
    # Command line arguments override last session
    override_session = args.classes or args.images or args.list
    
    if args.classes:
        if os.path.isfile(args.classes):
            controller._annotation_controller.load_class_names(args.classes)
        else:
            print(f"Warning: Class file not found: {args.classes}")
    
    if args.images:
        if os.path.isdir(args.images):
            controller._image_model.load_images_from_directory(args.images)
        else:
            print(f"Warning: Image directory not found: {args.images}")
    elif args.list:
        if os.path.isfile(args.list):
            controller._image_model.load_images_from_file_list(args.list, args.base_dir)
        else:
            print(f"Warning: Image list file not found: {args.list}")
    
    # Show message about session restoration
    if not override_session and controller._settings_model.has_previous_session():
        print("Restored last session. Use File menu to load different data if needed.")
    
    # Show main window
    controller.show()
    
    # Run application
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

