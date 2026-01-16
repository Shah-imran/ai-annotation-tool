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
                    self._settings = json.load(f)
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
            # Q&A settings
            "qa_enabled": False,
            "qa_questions_file": "",
            "qa_answers_folder": "",
            "recent_qa_questions_files": [],
            "recent_qa_answers_folders": []
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
