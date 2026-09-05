# -*- coding: utf-8 -*-
"""يبني جذر الفحص من مكان العمل.

مصدر الفحص هو lab/ لا الجذر: الجذر ما يراه الناس، والمختبر ما يُطوَّر.

    python3 tests/sync.py
"""
import shutil, sys
from harness import REPO, LAB, ROOT

ITEMS = ['index.html', 'admin.html', 'sw.js',
         'manifest.webmanifest', 'manifest-admin.webmanifest', 'assets']

def main():
    if not LAB.exists():
        sys.exit('✗ لا يوجد مجلّد lab/')
    ROOT.mkdir(parents=True, exist_ok=True)
    for it in ITEMS:
        src, dst = LAB / it, ROOT / it
        if not src.exists():
            continue
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    dev = ROOT / 'dev'
    if dev.exists():
        shutil.rmtree(dev)
    shutil.copytree(REPO / 'dev', dev)
    print(f'✓ {ROOT} ← lab/')

if __name__ == '__main__':
    main()
