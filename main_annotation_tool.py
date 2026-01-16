#!/usr/bin/env python3
"""
Main launcher for the Annotation Tool (Scan Lab).
This is a convenience script that can be run directly.
"""
import sys
import os

# Add the current directory to Python path so we can import annotation_tool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from annotation_tool.main import main

if __name__ == '__main__':
    main()

