# PyInstaller recipe for Erwin's Hypothesis.
# Build from the repository root:   pyinstaller packaging/ErwinsHypothesis.spec --noconfirm
# Output: dist/ErwinsHypothesis/ (Windows/Linux folder with the program) or dist/ErwinsHypothesis.app (Mac)
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
BACKEND = os.path.join(ROOT, "backend")

hidden = collect_submodules("uvicorn") + ["app.main", "app.desktop", "openpyxl"]
try:
    hidden += collect_submodules("webview")
except Exception:
    pass

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    pathex=[BACKEND],
    datas=[(os.path.join(BACKEND, "app", "static"), os.path.join("app", "static"))],
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "pandas", "IPython", "pytest", "plotly", "statsmodels",
              "pingouin", "lifelines", "notebook", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="ErwinsHypothesis",
    console=False,          # no black terminal window; logs go to the app's logs/ folder
    upx=False,              # UPX-compressed files trigger more antivirus false positives
)
coll = COLLECT(exe, a.binaries, a.datas, name="ErwinsHypothesis", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="ErwinsHypothesis.app",
        bundle_identifier="org.erwinshypothesis.app",
        info_plist={"CFBundleDisplayName": "Erwin's Hypothesis", "NSHighResolutionCapable": True,
                    "CFBundleShortVersionString": os.environ.get("EH_VERSION", "0.1.0")},
    )
