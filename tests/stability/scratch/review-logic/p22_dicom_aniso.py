"""Control: anisotropic 2-D DICOM (PixelSpacing [row=0.5, col=2.0]) exported through the dock → NIfTI zooms must be (x=2.0, y=0.5)."""
from common import *
import numpy as np, nibabel as nib, pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
d = os.path.join(SCR, "ws", "p22"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
rows, cols = 30, 40
ds = Dataset(); ds.file_meta = FileMetaDataset()
ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian; ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"; ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID; ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
ds.Modality = "OT"; ds.Rows = rows; ds.Columns = cols; ds.PixelSpacing = ["0.5", "2.0"]
ds.SamplesPerPixel = 1; ds.PhotometricInterpretation = "MONOCHROME2"; ds.BitsAllocated = 16; ds.BitsStored = 16; ds.HighBit = 15; ds.PixelRepresentation = 0
arr = (np.arange(rows * cols, dtype=np.uint16).reshape(rows, cols)); ds.PixelData = arr.tobytes()
ds.is_little_endian = True; ds.is_implicit_VR = False
ds.save_as(os.path.join(d, "aniso.dcm"), enforce_file_format=True)
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, d); cell = quad.active_cell(); c = cell.canvas(); sd = cell.series_data()
print("displayed", c.displayed_pixels().shape, "sd.pixel_spacing", sd.pixel_spacing)
dock._fmt_chk["nifti"].setChecked(True); dock._image_chk.setChecked(True)
H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.6,0.3)); dock._save(advance=False); app.processEvents()
out = nib.load(os.path.join(ws.out_dir, "nifti", "aniso_image.nii.gz")); zo = tuple(round(float(z),3) for z in out.header.get_zooms()[:2])
print("exported shape", out.shape, "zooms", zo)
check("2-D DICOM: exported zooms (x=col 2.0, y=row 0.5)", zo == (2.0, 0.5) and out.shape == (cols, rows, 1), f"{zo} {out.shape}")
win.close(); app.processEvents(); sys.exit(summary())
