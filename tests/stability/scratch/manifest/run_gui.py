"""Driver: run every t_gui.py scenario in its own process; record rc, stdout checks, filtered stderr."""
import subprocess, sys, os, re
PY = os.path.expanduser("~/miniconda3/envs/viewer_vidi/bin/python")
D = os.path.dirname(os.path.abspath(__file__))
NOISE = re.compile(r"propagateSizeHints|XDG_SESSION_TYPE")
SC = sys.argv[1:] or ["ro_outdir", "manifest_is_dir", "ro_after_subdirs", "extra_column", "bom_manifest",
                      "nonutf8_open", "nul_open", "outdir_change", "delete_source", "rectless_maskless",
                      "stale_files", "big_manifest", "unicode_stems", "tmp_leftover_gui"]
env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
for s in SC:
    for post in (False, True):
        args = ["timeout", "300", PY, os.path.join(D, "t_gui.py"), s] + (["post"] if post else [])
        p = subprocess.run(args, capture_output=True, text=True, env=env, cwd="/tmp")
        if post and "KeyError" in p.stderr and "_post" in p.stderr:
            continue                                     # no post step for this scenario
        err = "\n".join(l for l in p.stderr.splitlines() if l.strip() and not NOISE.search(l))
        print(f"\n### {s}{' (post)' if post else ''}  rc={p.returncode}")
        print(p.stdout.rstrip())
        if err:
            print("--- stderr ---"); print(err[-1500:])
