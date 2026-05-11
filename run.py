"""Self-contained launcher for viewer-vidi.

The package directory name contains a dash, so 'python -m viewer-vidi' is
invalid. This script registers the package as 'viewer_vidi' and runs __main__.
It lives inside viewer-vidi/ so it works without any parent-directory structure.
"""
import sys, os, types, importlib.util

viewer_src = os.path.dirname(os.path.abspath(__file__))

pkg = types.ModuleType('viewer_vidi')
pkg.__path__ = [viewer_src]
pkg.__package__ = 'viewer_vidi'
pkg.__file__ = os.path.join(viewer_src, '__init__.py')
sys.modules['viewer_vidi'] = pkg

init_spec = importlib.util.spec_from_file_location('viewer_vidi', pkg.__file__)
init_spec.loader.exec_module(pkg)

main_spec = importlib.util.spec_from_file_location(
    'viewer_vidi.__main__',
    os.path.join(viewer_src, '__main__.py'),
    submodule_search_locations=[],
)
main_mod = importlib.util.module_from_spec(main_spec)
main_mod.__package__ = 'viewer_vidi'
sys.modules['viewer_vidi.__main__'] = main_mod
main_spec.loader.exec_module(main_mod)
main_mod.main()
