# -*- coding: utf-8 -*-
"""يشغّل الطُّقُم كلَّها ويجمع النتيجة في سطرٍ واحد.

    python3 tests/sync.py && python3 tests/run.py            كلّها
    python3 tests/run.py check_month check_receipt2          طقمًا بعينه
    python3 tests/run.py --list                              الأسماء

ما يحتاج قاعدةً حيّة يُستثنى بذكره في NEEDS_DB أدناه؛ ولا يُشغَّل إلّا
بمفاتيح Supabase في البيئة.
"""
import pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
SUITES = sorted(p.stem for p in HERE.glob('check_*.py'))
SUITES += sorted(p.stem for p in HERE.glob('test*.py'))

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if '--list' in sys.argv:
        print('\n'.join(SUITES)); return 0
    todo = args or SUITES
    rows, t0 = [], time.time()
    for name in todo:
        f = HERE / f'{name}.py'
        if not f.exists():
            rows.append((name, None, 'غير موجود')); continue
        t = time.time()
        r = subprocess.run([sys.executable, str(f)], capture_output=True, text=True)
        tail = [l for l in r.stdout.strip().split('\n') if 'passed' in l]
        rows.append((name, r.returncode == 0,
                     (tail[-1] if tail else f'خرج بـ {r.returncode}') + f'  ({time.time()-t:.0f}ث)'))
        if r.returncode != 0:
            for l in r.stdout.split('\n'):
                if l.startswith('FAIL'):
                    rows.append(('', False, '    ' + l))

    print()
    ok = sum(1 for _, s, _ in rows if s)
    tot = sum(1 for n, s, _ in rows if n)
    for name, state, note in rows:
        mark = '✓' if state else ('✗' if state is False else '·')
        print(f'{mark} {name:<18} {note}' if name else f'  {note}')
    print(f'\n=== {ok}/{tot} طقمًا نجح — {time.time()-t0:.0f} ثانية ===')
    return 0 if ok == tot else 1

if __name__ == '__main__':
    sys.exit(main())
