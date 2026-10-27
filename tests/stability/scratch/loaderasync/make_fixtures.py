"""Build synthetic / corrupted fixtures for the loaderasync lens (no Qt)."""
import os, shutil, stat, sys
import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
import nibabel as nib
from PIL import Image

ROOT = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx"
FIX = "/media/zsk/ressd/research/alldata_backup/dicom/original"
MR  = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOM/26070517/54450002"
CNII = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
PNG_RGBA = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"

def mk(d):
    os.makedirs(d, exist_ok=True); return d

def fresh(d):
    if os.path.isdir(d):
        # restore perms before rmtree (chmod 000 fixtures)
        for dp, dn, fn in os.walk(d):
            for f in fn:
                try: os.chmod(os.path.join(dp, f), 0o644)
                except OSError: pass
        shutil.rmtree(d)
    return mk(d)

def synth_dicom(path, arr, photometric="MONOCHROME2", frames=None, spacing=(0.5, 0.25)):
    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
    fm.MediaStorageSOPInstanceUID = generate_uid()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(path, {}, file_meta=fm, preamble=b"\0" * 128)
    ds.SOPClassUID = fm.MediaStorageSOPClassUID
    ds.SOPInstanceUID = fm.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid(); ds.SeriesInstanceUID = generate_uid()
    ds.PatientName = "SYN"; ds.PatientID = "0"; ds.Modality = "OT"
    ds.SamplesPerPixel = 1; ds.PhotometricInterpretation = photometric
    ds.BitsAllocated = 16; ds.BitsStored = 16; ds.HighBit = 15; ds.PixelRepresentation = 0
    ds.PixelSpacing = [str(spacing[0]), str(spacing[1])]
    if frames:
        ds.NumberOfFrames = frames
        ds.Rows, ds.Columns = arr.shape[1], arr.shape[2]
    else:
        ds.Rows, ds.Columns = arr.shape
    ds.PixelData = np.ascontiguousarray(arr.astype(np.uint16)).tobytes()
    ds.is_little_endian = True; ds.is_implicit_VR = False
    ds.save_as(path, enforce_file_format=True)

def main():
    fresh(ROOT)
    # ── A: shapes workspace: small PNG + big DICOM (alternating-shape test) ──
    d = mk(os.path.join(ROOT, "shapes"))
    g = (np.linspace(0, 255, 300 * 200).reshape(200, 300)).astype(np.uint8)   # 300x200 (W x H)
    Image.fromarray(g, "L").save(os.path.join(d, "a_small.png"))
    shutil.copy(os.path.join(FIX, "bpd1_20100101_1.dcm"), os.path.join(d, "b_big.dcm"))
    Image.fromarray(g.T.copy(), "L").save(os.path.join(d, "c_small_t.png"))               # 200x300
    shutil.copy(os.path.join(FIX, "bpd1_20100102_1.dcm"), os.path.join(d, "d_big2.dcm"))   # 2570x2040

    # ── B: rapid-nav workspace: 6 CR DICOMs (two different shapes) ──
    d = mk(os.path.join(ROOT, "rapid"))
    for f in ("bpd1_20100101_1.dcm", "bpd1_20100101_2.dcm", "bpd1_20100102_1.dcm",
              "bpd1_20100103_1.dcm", "bpd1_20100104_1.dcm", "bpd1_20100105_1.dcm"):
        src = os.path.join(FIX, f)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(d, f))

    # ── C: error workspace ──
    d = mk(os.path.join(ROOT, "errors"))
    good = os.path.join(FIX, "bpd1_20100101_1.dcm")
    shutil.copy(good, os.path.join(d, "00_good.dcm"))
    with open(os.path.join(d, "01_garbage.dcm"), "wb") as f:
        f.write(os.urandom(4096))
    with open(good, "rb") as f:
        head = f.read(2048)
    with open(os.path.join(d, "02_trunc2k.dcm"), "wb") as f:
        f.write(head)
    # truncated inside pixel data (header intact, half the pixels)
    with open(good, "rb") as f:
        half = f.read(4540 + (2044 * 1514 * 2) // 2)
    with open(os.path.join(d, "03_trunc_half.dcm"), "wb") as f:
        f.write(half)
    open(os.path.join(d, "04_empty.png"), "wb").close()
    shutil.copy(good, os.path.join(d, "05_noperm.dcm"))
    os.chmod(os.path.join(d, "05_noperm.dcm"), 0)
    shutil.copy(good, os.path.join(d, "06_good2.dcm"))

    # ── D: formats workspace ──
    d = mk(os.path.join(ROOT, "formats"))
    shutil.copy(CNII, os.path.join(d, "c3d.nii"))
    # 2-D anisotropic NIfTI (X=40, Y=30), zooms (0.5, 2.0)
    a2 = np.arange(40 * 30, dtype=np.float32).reshape(40, 30)
    nib.save(nib.Nifti1Image(a2, np.diag([0.5, 2.0, 1.0, 1.0])), os.path.join(d, "n2d_aniso.nii.gz"))
    # 3-D anisotropic NIfTI (X=40, Y=30, Z=5), zooms (0.5, 2.0, 3.0)
    a3 = np.arange(40 * 30 * 5, dtype=np.float32).reshape(40, 30, 5)
    nib.save(nib.Nifti1Image(a3, np.diag([0.5, 2.0, 3.0, 1.0])), os.path.join(d, "n3d_aniso.nii.gz"))
    shutil.copy(PNG_RGBA, os.path.join(d, "rgba.png"))
    # 16-bit PNG 64x48 with values up to 60000
    p16 = (np.linspace(0, 60000, 48 * 64).reshape(48, 64)).astype(np.uint16)
    Image.fromarray(p16, "I;16").save(os.path.join(d, "p16.png"))
    # LA (grey + alpha) PNG
    la = np.zeros((48, 64, 2), np.uint8); la[..., 0] = 128; la[..., 1] = 255
    Image.fromarray(la, "LA").save(os.path.join(d, "la.png"))
    # multi-frame DICOM: 3 frames 50x60, frame k = k*1000 + gradient
    mf = np.stack([np.full((50, 60), k * 1000, np.uint16) + np.arange(60, dtype=np.uint16)[None, :]
                   for k in range(3)])
    synth_dicom(os.path.join(d, "multiframe.dcm"), mf, frames=3)
    # MONOCHROME1 vs MONOCHROME2 synthetic pair with identical pixel data
    gr = (np.linspace(0, 4000, 50 * 60).reshape(50, 60)).astype(np.uint16)
    synth_dicom(os.path.join(d, "mono1.dcm"), gr, photometric="MONOCHROME1")
    synth_dicom(os.path.join(d, "mono2.dcm"), gr, photometric="MONOCHROME2")

    # ── E: extensionless MR subset (20 files) ──
    d = mk(os.path.join(ROOT, "extless", "54450002"))
    names = sorted(os.listdir(MR))[:20]
    for n in names:
        shutil.copy(os.path.join(MR, n), os.path.join(d, n))

    # ── F: list workspace with a series-directory entry ──
    d = mk(os.path.join(ROOT, "listdir"))
    with open(os.path.join(d, "items.txt"), "w") as f:
        f.write("# list with a dir entry\n")
        f.write(os.path.join(ROOT, "extless", "54450002") + "\n")       # directory
        f.write(os.path.join(ROOT, "extless", "54450002", names[0]) + "\n")  # extensionless file
        f.write(os.path.join(FIX, "bpd1_20100101_2.dcm") + "\n")
    print("fixtures built under", ROOT)

if __name__ == "__main__":
    main()
