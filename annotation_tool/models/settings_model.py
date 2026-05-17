"""
Settings model for storing and retrieving application preferences.
"""
import json
import os
import sys
from typing import Optional, Dict, Any
from PyQt5.QtCore import QObject, pyqtSignal, QStandardPaths


class SettingsModel(QObject):
    """
    Model for managing application settings and preferences.
    Stores last used paths, window settings, and user preferences.
    """
    
    # Signals
    settings_changed = pyqtSignal()
    settings_loaded_from_file = pyqtSignal(str)  # Emitted when settings are loaded from a custom file
    
    def __init__(self):
        super().__init__()
        self._settings: Dict[str, Any] = {}
        # Check if there's a saved custom settings file path
        custom_path = self._get_saved_settings_file_path()
        if custom_path and os.path.exists(custom_path):
            self._settings_file = custom_path
        else:
            self._settings_file = self._get_settings_file_path()
        self._load_settings()
    
    def _is_bundled(self) -> bool:
        """Check if running as a PyInstaller bundled executable."""
        return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    
    def _get_exe_directory(self) -> str:
        """Get the directory where the executable is located (not temp directory)."""
        if self._is_bundled():
            # When bundled, sys.executable points to the exe file
            # sys._MEIPASS points to the temp extraction directory (which we want to avoid)
            exe_path = sys.executable
            exe_dir = os.path.dirname(os.path.abspath(exe_path))
            
            # Verify it's not the temp directory (check for PyInstaller temp patterns)
            temp_indicators = ['_MEI', 'Temp', 'tmp', 'AppData\\Local\\Temp']
            is_temp_dir = any(indicator in exe_dir for indicator in temp_indicators)
            
            if not is_temp_dir:
                return exe_dir
            
            # If sys.executable is in temp, try sys.argv[0]
            if len(sys.argv) > 0:
                argv0_path = os.path.abspath(sys.argv[0])
                argv0_dir = os.path.dirname(argv0_path)
                is_temp_dir = any(indicator in argv0_dir for indicator in temp_indicators)
                if not is_temp_dir:
                    return argv0_dir
        
        # Fallback: use current working directory
        return os.getcwd()
    
    def _get_settings_location_file(self) -> str:
        """Get the path to the file that stores the custom settings file location."""
        # Store in a known location (AppData or next to exe)
        if self._is_bundled():
            # Try AppData first
            try:
                app_data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
                if app_data_dir:
                    return os.path.join(app_data_dir, ".settings_location")
            except Exception:
                pass
            
            # Fallback to exe directory
            exe_dir = self._get_exe_directory()
            return os.path.join(exe_dir, ".settings_location")
        else:
            # Development: use project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            return os.path.join(project_root, ".settings_location")
    
    def _get_saved_settings_file_path(self) -> Optional[str]:
        """Get the saved custom settings file path if it exists."""
        location_file = self._get_settings_location_file()
        try:
            if os.path.exists(location_file):
                with open(location_file, 'r', encoding='utf-8') as f:
                    saved_path = f.read().strip()
                    if saved_path and os.path.exists(saved_path):
                        return saved_path
        except Exception as e:
            print(f"Error reading settings location file: {e}")
        return None
    
    def _save_settings_file_path(self, file_path: str):
        """Save the custom settings file path for future use."""
        location_file = self._get_settings_location_file()
        try:
            os.makedirs(os.path.dirname(location_file), exist_ok=True)
            with open(location_file, 'w', encoding='utf-8') as f:
                f.write(file_path)
        except Exception as e:
            print(f"Error saving settings location file: {e}")
    
    def _get_settings_file_path(self) -> str:
        """Get the path to the settings file."""
        # When bundled as exe, use exe's directory or AppData
        if self._is_bundled():
            # First try: Use AppData directory (most reliable for bundled apps)
            # This ensures settings persist even if exe is moved or in Program Files
            try:
                app_data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
                if app_data_dir:
                    settings_dir = app_data_dir
                    os.makedirs(settings_dir, exist_ok=True)
                    return os.path.join(settings_dir, "settings.json")
            except Exception as e:
                print(f"Error using AppData directory: {e}")
            
            # Second try: Use directory next to exe (portable option)
            try:
                exe_dir = self._get_exe_directory()
                settings_dir = os.path.join(exe_dir, "settings")
                os.makedirs(settings_dir, exist_ok=True)
                return os.path.join(settings_dir, "settings.json")
            except Exception as e:
                print(f"Error creating settings directory next to exe: {e}")
            
            # Final fallback: current working directory
            settings_dir = os.path.join(os.getcwd(), "settings")
            os.makedirs(settings_dir, exist_ok=True)
            return os.path.join(settings_dir, "settings.json")
        else:
            # Development mode: use project root directory
            # Find the project root by looking for main_annotation_tool.py or annotation_tool directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Go up from annotation_tool/models/ to project root
            project_root = os.path.dirname(os.path.dirname(current_dir))
            
            # Create settings directory in project root
            settings_dir = os.path.join(project_root, "settings")
            
            try:
                os.makedirs(settings_dir, exist_ok=True)
            except Exception as e:
                print(f"Error creating settings directory: {e}")
                # Fallback to current working directory
                settings_dir = os.path.join(os.getcwd(), "settings")
                os.makedirs(settings_dir, exist_ok=True)
            
            return os.path.join(settings_dir, "settings.json")
    
    def _load_settings(self):
        """Load settings from file."""
        try:
            if os.path.exists(self._settings_file):
                with open(self._settings_file, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                keys_from_file = set(raw.keys())
                self._settings = raw
                defaults = self._get_default_settings()
                for key, value in defaults.items():
                    if key not in self._settings:
                        self._settings[key] = value
                if "volume_preview_stride_z" not in keys_from_file or "volume_preview_stride_xy" not in keys_from_file:
                    self._backfill_volume_preview_strides_from_level()
                    self._save_settings()
            else:
                # Initialize with default settings
                self._settings = self._get_default_settings()
                self._save_settings()
        except Exception as e:
            print(f"Error loading settings: {e}")
            self._settings = self._get_default_settings()
    
    def _save_settings(self):
        """Save settings to file."""
        try:
            os.makedirs(os.path.dirname(self._settings_file), exist_ok=True)
            with open(self._settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            self.settings_changed.emit()
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings."""
        return {
            "last_image_directory": "",
            "last_image_list_file": "",
            "last_classes_file": "",
            "last_base_directory": "",
            "window_geometry": {
                "x": 100,
                "y": 100,
                "width": 1400,
                "height": 800
            },
            "recent_image_directories": [],
            "recent_classes_files": [],
            "max_recent_items": 5,
            "auto_load_last_session": True,
            "auto_save_interval": 30,  # seconds
            "copy_boxes_count": 1,  # Number of images to copy boxes to
            "sidebar_width": 0,  # Sidebar width (0 means use default)
            # Q&A settings
            "qa_enabled": False,
            "qa_questions_file": "",
            "qa_answers_folder": "",
            "recent_qa_questions_files": [],
            "recent_qa_answers_folders": [],
            # Volume / 3D annotation
            "last_annotation_mode": "2d",
            "last_volume_scan_dir": "",
            "last_volume_slice_index": 0,
            "annotations_output_directory": "",
            "voxel_spacing": [1.0, 1.0, 1.0],
            "volume_brush_radius": 8,
            "volume_class_id": 1,
            "volume_splitter_vertical": [280, 520],
            "volume_splitter_horizontal": [800, 320],
            "volume_preview_collapsed": False,
            "volume_slice_collapsed": False,
            "volume_preview_level": 5,
            "volume_preview_limit_z_range": False,
            "volume_preview_z_start": 0,
            "volume_preview_z_end": -1,
            "volume_preview_native_resolution": False,
            "volume_preview_stride_z": 1,
            "volume_preview_stride_xy": 1,
            # 3D preview — currently selected mode + point-cloud parameters.
            "volume_preview_mode": "isosurface_lit",
            "volume_preview_point_size": 3.0,              # 1.0–20.0
            "volume_preview_point_threshold_auto": True,
            "volume_preview_point_threshold": 25,          # 0–255
            "volume_preview_iso_color": "#dcdcdc",         # `#RRGGBB`, isosurface mesh color
            "volume_preview_show_mask": True,
            "volume_preview_brightness_percent": 100,      # 10–250, 100 = default
            "volume_preview_export_snapshot_dir": "",
            "volume_preview_export_mesh_dir": "",
        }
    
    # Image directory settings
    def get_last_image_directory(self) -> str:
        """Get last used image directory."""
        return self._settings.get("last_image_directory", "")
    
    def set_last_image_directory(self, directory: str):
        """Set last used image directory."""
        if directory and os.path.isdir(directory):
            self._settings["last_image_directory"] = directory
            self._add_to_recent_list("recent_image_directories", directory)
            self._save_settings()
    
    def get_recent_image_directories(self) -> list:
        """Get list of recent image directories."""
        return self._settings.get("recent_image_directories", [])
    
    # Image list file settings
    def get_last_image_list_file(self) -> str:
        """Get last used image list file."""
        return self._settings.get("last_image_list_file", "")
    
    def set_last_image_list_file(self, file_path: str):
        """Set last used image list file."""
        if file_path and os.path.isfile(file_path):
            self._settings["last_image_list_file"] = file_path
            self._save_settings()
    
    def get_last_base_directory(self) -> str:
        """Get last used base directory for relative paths."""
        return self._settings.get("last_base_directory", "")
    
    def set_last_base_directory(self, directory: str):
        """Set last used base directory."""
        if directory:
            self._settings["last_base_directory"] = directory
            self._save_settings()
    
    # Classes file settings
    def get_last_classes_file(self) -> str:
        """Get last used classes file."""
        return self._settings.get("last_classes_file", "")
    
    def set_last_classes_file(self, file_path: str):
        """Set last used classes file."""
        if file_path and os.path.isfile(file_path):
            self._settings["last_classes_file"] = file_path
            self._add_to_recent_list("recent_classes_files", file_path)
            self._save_settings()
    
    def get_recent_classes_files(self) -> list:
        """Get list of recent classes files."""
        return self._settings.get("recent_classes_files", [])
    
    # Window settings
    def get_window_geometry(self) -> Dict[str, int]:
        """Get last window geometry."""
        return self._settings.get("window_geometry", {"x": 100, "y": 100, "width": 1400, "height": 800})
    
    def set_window_geometry(self, x: int, y: int, width: int, height: int):
        """Set window geometry."""
        self._settings["window_geometry"] = {
            "x": x, "y": y, "width": width, "height": height
        }
        self._save_settings()
    
    # General settings
    def get_auto_load_last_session(self) -> bool:
        """Check if auto-load last session is enabled."""
        return self._settings.get("auto_load_last_session", True)
    
    def set_auto_load_last_session(self, enabled: bool):
        """Set auto-load last session preference."""
        self._settings["auto_load_last_session"] = enabled
        self._save_settings()
    
    def get_auto_save_interval(self) -> int:
        """Get auto-save interval in seconds."""
        return self._settings.get("auto_save_interval", 30)
    
    def set_auto_save_interval(self, interval: int):
        """Set auto-save interval in seconds."""
        self._settings["auto_save_interval"] = max(1, interval)
        self._save_settings()
    
    def get_max_recent_items(self) -> int:
        """Get maximum number of recent items to remember."""
        return self._settings.get("max_recent_items", 5)
    
    def set_max_recent_items(self, max_items: int):
        """Set maximum number of recent items to remember."""
        self._settings["max_recent_items"] = max(1, min(20, max_items))
        self._save_settings()
    
    def get_copy_boxes_count(self) -> int:
        """Get number of images to copy boxes to."""
        return self._settings.get("copy_boxes_count", 1)
    
    def set_copy_boxes_count(self, count: int):
        """Set number of images to copy boxes to."""
        # Allow any positive value here; the actual copy operation will
        # clamp to the number of available images, so there's no need
        # to enforce an arbitrary upper limit in settings.
        try:
            safe_count = int(count)
        except (TypeError, ValueError):
            safe_count = 1
        self._settings["copy_boxes_count"] = max(1, safe_count)
        self._save_settings()
    
    def get_sidebar_width(self) -> int:
        """Get saved sidebar width."""
        return self._settings.get("sidebar_width", 0)
    
    def set_sidebar_width(self, width: int):
        """Set sidebar width."""
        if width > 0:
            self._settings["sidebar_width"] = width
            self._save_settings()

    # Volume / 3D annotation settings
    def get_last_annotation_mode(self) -> str:
        return self._settings.get("last_annotation_mode", "2d")

    def set_last_annotation_mode(self, mode: str):
        if mode in ("2d", "3d"):
            self._settings["last_annotation_mode"] = mode
            self._save_settings()

    def get_last_volume_scan_dir(self) -> str:
        return self._settings.get("last_volume_scan_dir", "")

    def set_last_volume_scan_dir(self, directory: str):
        if directory and os.path.isdir(directory):
            self._settings["last_volume_scan_dir"] = directory
            self._save_settings()

    def get_annotations_output_directory(self) -> str:
        return self._settings.get("annotations_output_directory", "")

    def set_annotations_output_directory(self, directory: str):
        if directory:
            normalized = os.path.normpath(directory)
            self._settings["annotations_output_directory"] = normalized
            self._save_settings()

    def get_last_volume_slice_index(self) -> int:
        try:
            return max(0, int(self._settings.get("last_volume_slice_index", 0)))
        except (TypeError, ValueError):
            return 0

    def set_last_volume_slice_index(self, index: int):
        try:
            self._settings["last_volume_slice_index"] = max(0, int(index))
            self._save_settings()
        except (TypeError, ValueError):
            pass

    def get_volume_brush_radius(self) -> int:
        try:
            return max(1, min(128, int(self._settings.get("volume_brush_radius", 8))))
        except (TypeError, ValueError):
            return 8

    def set_volume_brush_radius(self, radius: int):
        try:
            self._settings["volume_brush_radius"] = max(1, min(128, int(radius)))
            self._save_settings()
        except (TypeError, ValueError):
            pass

    def get_volume_class_id(self) -> int:
        try:
            return max(0, int(self._settings.get("volume_class_id", 1)))
        except (TypeError, ValueError):
            return 1

    def set_volume_class_id(self, class_id: int):
        try:
            self._settings["volume_class_id"] = max(0, int(class_id))
            self._save_settings()
        except (TypeError, ValueError):
            pass

    def get_volume_splitter_vertical(self) -> list:
        return list(self._settings.get("volume_splitter_vertical", [280, 520]))

    def get_volume_splitter_horizontal(self) -> list:
        return list(self._settings.get("volume_splitter_horizontal", [800, 320]))

    def set_volume_splitter_vertical(self, sizes: list) -> None:
        if len(sizes) == 2 and all(isinstance(s, int) and s >= 0 for s in sizes):
            self._settings["volume_splitter_vertical"] = [int(sizes[0]), int(sizes[1])]
            self._save_settings()

    def set_volume_splitter_horizontal(self, sizes: list) -> None:
        if len(sizes) == 2 and all(isinstance(s, int) and s >= 0 for s in sizes):
            self._settings["volume_splitter_horizontal"] = [int(sizes[0]), int(sizes[1])]
            self._save_settings()

    def get_volume_preview_collapsed(self) -> bool:
        return bool(self._settings.get("volume_preview_collapsed", False))

    def get_volume_slice_collapsed(self) -> bool:
        return bool(self._settings.get("volume_slice_collapsed", False))

    def set_volume_preview_collapsed(self, collapsed: bool) -> None:
        self._settings["volume_preview_collapsed"] = bool(collapsed)
        self._save_settings()

    def set_volume_slice_collapsed(self, collapsed: bool) -> None:
        self._settings["volume_slice_collapsed"] = bool(collapsed)
        self._save_settings()

    def get_volume_preview_level(self) -> int:
        if "volume_preview_level" in self._settings:
            try:
                return max(1, min(5, int(self._settings["volume_preview_level"])))
            except (TypeError, ValueError):
                pass
        if "volume_preview_quality" in self._settings:
            q = self._settings.get("volume_preview_quality")
            if q == "fast":
                return 2
            if q == "full":
                return 5
        return 5

    def set_volume_preview_level(self, level: int) -> None:
        self._settings["volume_preview_level"] = max(1, min(5, int(level)))
        self._save_settings()

    def _backfill_volume_preview_strides_from_level(self) -> None:
        """Map legacy 1–5 quality to Z / XY stride (called once when upgrading settings file)."""
        try:
            lev = max(1, min(5, int(self._settings.get("volume_preview_level", 5))))
        except (TypeError, ValueError):
            lev = 5
        z_map = {5: 1, 4: 1, 3: 2, 2: 2, 1: 4}
        xy_map = {5: 1, 4: 2, 3: 4, 2: 8, 1: 12}
        self._settings["volume_preview_stride_z"] = z_map.get(lev, 1)
        self._settings["volume_preview_stride_xy"] = xy_map.get(lev, 1)

    def get_volume_preview_stride_z(self) -> int:
        try:
            return max(1, min(32, int(self._settings.get("volume_preview_stride_z", 1))))
        except (TypeError, ValueError):
            return 1

    def get_volume_preview_stride_xy(self) -> int:
        try:
            return max(1, min(32, int(self._settings.get("volume_preview_stride_xy", 1))))
        except (TypeError, ValueError):
            return 1

    def set_volume_preview_stride_z(self, stride: int) -> None:
        self._settings["volume_preview_stride_z"] = max(1, min(32, int(stride)))
        self._save_settings()

    def set_volume_preview_stride_xy(self, stride: int) -> None:
        self._settings["volume_preview_stride_xy"] = max(1, min(32, int(stride)))
        self._save_settings()

    def get_volume_preview_limit_z_range(self) -> bool:
        return bool(self._settings.get("volume_preview_limit_z_range", False))

    def set_volume_preview_limit_z_range(self, enabled: bool) -> None:
        self._settings["volume_preview_limit_z_range"] = bool(enabled)
        self._save_settings()

    def get_volume_preview_z_start(self) -> int:
        try:
            return max(0, int(self._settings.get("volume_preview_z_start", 0)))
        except (TypeError, ValueError):
            return 0

    def set_volume_preview_z_start(self, index: int) -> None:
        self._settings["volume_preview_z_start"] = max(0, int(index))
        self._save_settings()

    def get_volume_preview_z_end(self) -> int:
        try:
            return int(self._settings.get("volume_preview_z_end", -1))
        except (TypeError, ValueError):
            return -1

    def set_volume_preview_z_end(self, index: int) -> None:
        self._settings["volume_preview_z_end"] = int(index)
        self._save_settings()

    def get_volume_preview_native_resolution(self) -> bool:
        return bool(self._settings.get("volume_preview_native_resolution", False))

    def set_volume_preview_native_resolution(self, enabled: bool) -> None:
        self._settings["volume_preview_native_resolution"] = bool(enabled)
        self._save_settings()

    # --- Mode + per-mode parameters ---------------------------------------

    _VALID_PREVIEW_MODES = ("isosurface_lit", "point_cloud")

    def get_volume_preview_mode(self) -> str:
        mode = str(self._settings.get("volume_preview_mode", "isosurface_lit"))
        if mode not in self._VALID_PREVIEW_MODES:
            mode = "isosurface_lit"
        return mode

    def set_volume_preview_mode(self, mode: str) -> None:
        if mode in self._VALID_PREVIEW_MODES:
            self._settings["volume_preview_mode"] = mode
            self._save_settings()

    def get_volume_preview_point_size(self) -> float:
        try:
            return max(1.0, min(20.0, float(self._settings.get("volume_preview_point_size", 3.0))))
        except (TypeError, ValueError):
            return 3.0

    def set_volume_preview_point_size(self, value: float) -> None:
        self._settings["volume_preview_point_size"] = max(1.0, min(20.0, float(value)))
        self._save_settings()

    def get_volume_preview_point_threshold_auto(self) -> bool:
        return bool(self._settings.get("volume_preview_point_threshold_auto", True))

    def set_volume_preview_point_threshold_auto(self, enabled: bool) -> None:
        self._settings["volume_preview_point_threshold_auto"] = bool(enabled)
        self._save_settings()

    def get_volume_preview_point_threshold(self) -> int:
        try:
            return max(0, min(255, int(self._settings.get("volume_preview_point_threshold", 25))))
        except (TypeError, ValueError):
            return 25

    def set_volume_preview_point_threshold(self, value: int) -> None:
        self._settings["volume_preview_point_threshold"] = max(0, min(255, int(value)))

    def get_volume_preview_iso_color(self) -> str:
        value = str(self._settings.get("volume_preview_iso_color", "#dcdcdc"))
        if not (value.startswith("#") and len(value) == 7):
            return "#dcdcdc"
        try:
            int(value[1:], 16)
        except ValueError:
            return "#dcdcdc"
        return value

    def set_volume_preview_iso_color(self, value: str) -> None:
        text = (value or "").strip()
        if not (text.startswith("#") and len(text) == 7):
            text = "#dcdcdc"
        else:
            try:
                int(text[1:], 16)
            except ValueError:
                text = "#dcdcdc"
        self._settings["volume_preview_iso_color"] = text
        self._save_settings()

    def get_volume_preview_show_mask(self) -> bool:
        return bool(self._settings.get("volume_preview_show_mask", True))

    def set_volume_preview_show_mask(self, enabled: bool) -> None:
        self._settings["volume_preview_show_mask"] = bool(enabled)
        self._save_settings()

    def get_volume_preview_brightness_percent(self) -> int:
        try:
            return max(10, min(250, int(self._settings.get("volume_preview_brightness_percent", 100))))
        except (TypeError, ValueError):
            return 100

    def set_volume_preview_brightness_percent(self, percent: int) -> None:
        self._settings["volume_preview_brightness_percent"] = max(10, min(250, int(percent)))
        self._save_settings()

    def get_volume_preview_export_snapshot_dir(self) -> str:
        return str(self._settings.get("volume_preview_export_snapshot_dir", "") or "")

    def set_volume_preview_export_snapshot_dir(self, directory: str) -> None:
        self._settings["volume_preview_export_snapshot_dir"] = (directory or "").strip()
        self._save_settings()

    def get_volume_preview_export_mesh_dir(self) -> str:
        return str(self._settings.get("volume_preview_export_mesh_dir", "") or "")

    def set_volume_preview_export_mesh_dir(self, directory: str) -> None:
        self._settings["volume_preview_export_mesh_dir"] = (directory or "").strip()
        self._save_settings()

    def get_voxel_spacing(self) -> list:
        return self._settings.get("voxel_spacing", [1.0, 1.0, 1.0])

    def set_voxel_spacing(self, spacing: list):
        if len(spacing) == 3:
            self._settings["voxel_spacing"] = [float(spacing[0]), float(spacing[1]), float(spacing[2])]
            self._save_settings()

    # Helper methods
    def _add_to_recent_list(self, key: str, item: str):
        """Add item to recent list, maintaining max size."""
        if key not in self._settings:
            self._settings[key] = []
        
        recent_list = self._settings[key]
        
        # Remove if already exists
        if item in recent_list:
            recent_list.remove(item)
        
        # Add to front
        recent_list.insert(0, item)
        
        # Limit size
        max_items = self._settings.get("max_recent_items", 5)
        self._settings[key] = recent_list[:max_items]
    
    def clear_recent_lists(self):
        """Clear all recent lists."""
        self._settings["recent_image_directories"] = []
        self._settings["recent_classes_files"] = []
        self._save_settings()
    
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self._settings = self._get_default_settings()
        self._save_settings()
    
    def has_previous_session(self) -> bool:
        """Check if there's a previous session to restore."""
        return bool(
            self.get_last_image_directory() or 
            self.get_last_image_list_file() or 
            self.get_last_classes_file()
        )
    
    def get_settings_file_path(self) -> str:
        """Get the path to the settings file for debugging."""
        return self._settings_file
    
    def load_settings_from_file(self, file_path: str) -> bool:
        """
        Load settings from a custom file path.
        
        Args:
            file_path: Path to the settings JSON file to load
            
        Returns:
            True if settings were loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
            
            # Validate that it's a dictionary
            if not isinstance(loaded_settings, dict):
                return False
            
            # Merge loaded settings with current settings (loaded settings take precedence)
            self._settings.update(loaded_settings)
            
            # Update the settings file path to the loaded file
            self._settings_file = file_path
            
            # Save the path to the location file so it's remembered on restart
            self._save_settings_file_path(file_path)
            
            # Save to the new location to persist the change
            self._save_settings()
            
            # Emit signal to notify that settings were loaded
            self.settings_loaded_from_file.emit(file_path)
            self.settings_changed.emit()
            
            return True
        except Exception as e:
            print(f"Error loading settings from file: {e}")
            return False
    
    def save_settings_to_file(self, file_path: str) -> bool:
        """
        Save current settings to a custom file path.
        
        Args:
            file_path: Path where to save the settings JSON file
            
        Returns:
            True if settings were saved successfully, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            
            # Update the settings file path to the saved file
            self._settings_file = file_path
            
            # Save the path to the location file so it's remembered on restart
            self._save_settings_file_path(file_path)
            
            self.settings_changed.emit()
            return True
        except Exception as e:
            print(f"Error saving settings to file: {e}")
            return False
    
    # Q&A settings
    def get_qa_enabled(self) -> bool:
        """Get Q&A feature enabled status."""
        return self._settings.get("qa_enabled", False)
    
    def set_qa_enabled(self, enabled: bool):
        """Set Q&A feature enabled status."""
        self._settings["qa_enabled"] = enabled
        self._save_settings()
    
    def get_qa_questions_file(self) -> str:
        """Get last used Q&A questions file."""
        return self._settings.get("qa_questions_file", "")
    
    def set_qa_questions_file(self, file_path: str):
        """Set last used Q&A questions file."""
        if file_path and os.path.isfile(file_path):
            self._settings["qa_questions_file"] = file_path
            self._add_to_recent_list("recent_qa_questions_files", file_path)
            self._save_settings()
    
    def get_recent_qa_questions_files(self) -> list:
        """Get list of recent Q&A questions files."""
        return self._settings.get("recent_qa_questions_files", [])
    
    def get_qa_answers_folder(self) -> str:
        """Get Q&A answers save folder."""
        return self._settings.get("qa_answers_folder", "")
    
    def set_qa_answers_folder(self, folder_path: str):
        """Set Q&A answers save folder."""
        if folder_path and os.path.isdir(folder_path):
            self._settings["qa_answers_folder"] = folder_path
            self._add_to_recent_list("recent_qa_answers_folders", folder_path)
            self._save_settings()
    
    def get_recent_qa_answers_folders(self) -> list:
        """Get list of recent Q&A answers folders."""
        return self._settings.get("recent_qa_answers_folders", [])
