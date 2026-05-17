"""
Round-trip tests for NIfTI segmentation save/load.
"""
import os
import tempfile
import unittest

import numpy as np

try:
    import nibabel  # noqa: F401

    HAS_NIBABEL = True
except ImportError:
    HAS_NIBABEL = False

from annotation_tool.services.volume_io import (
    load_segmentation_nifti,
    save_segmentation_nifti,
)


@unittest.skipUnless(HAS_NIBABEL, "nibabel not installed")
class TestVolumeIoNifti(unittest.TestCase):
    def test_roundtrip_uint8_labels(self):
        volume = np.zeros((4, 8, 16), dtype=np.uint8)
        volume[0, 2:4, 3:6] = 1
        volume[1, :, :] = 5
        volume[2, 1, 1] = 7
        spacing = (0.5, 1.0, 2.0)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "labels.nii.gz")
            save_segmentation_nifti(volume, path, spacing)
            self.assertTrue(os.path.isfile(path))

            loaded = load_segmentation_nifti(path)
            self.assertEqual(loaded.shape, volume.shape)
            self.assertEqual(loaded.dtype, np.uint8)
            np.testing.assert_array_equal(loaded, volume)

    def test_load_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_segmentation_nifti("/nonexistent/path/seg.nii.gz")


if __name__ == "__main__":
    unittest.main()
