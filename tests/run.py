import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-p', 'test_*.py', '-v'], cwd=root, check=True)
with tempfile.TemporaryDirectory() as directory:
    target = Path(directory) / 'release'
    subprocess.run([sys.executable, '-B', 'setup.py', 'export', '--output', str(target)], cwd=root, check=True)
    subprocess.run(['omarchy', 'plugin', 'validate', str(target)], check=True)
env = os.environ | {'QT_QPA_PLATFORM': 'offscreen', 'QT_QPA_PLATFORMTHEME': 'generic', 'QT_QUICK_CONTROLS_STYLE': 'Basic'}
subprocess.run(['/usr/lib/qt6/bin/qmltestrunner', '-input', 'tests/qml', '-import', 'tests/qml'], cwd=root, env=env, check=True)
