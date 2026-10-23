#!/usr/bin/env python3
"""MNOVA IR/MS converter — validated for the supplied butanoic_acid.mnova only.

GUI: python MNOVA_IR_MS_Converter.py
CLI: python MNOVA_IR_MS_Converter.py path/to/file.mnova [another.mnova ...]
No third-party Python packages required.
"""
import csv
import hashlib
import math
import struct
import sys
from pathlib import Path

KNOWN_SHA256 = 'dfccec3065af799dd49c87872d4abad15db4791593872d4d9aa4a538a0b410a7'


def extract(data):
    if hashlib.sha256(data).hexdigest() != KNOWN_SHA256:
        raise ValueError('Unsupported MNOVA layout: this version is validated only for the supplied butanoic_acid.mnova. No output was written.')
    n = 3551
    ir = struct.unpack_from('>3551d', data, 33949)
    ir_copy = struct.unpack_from('>3551d', data, 90773)
    if ir != ir_copy or not all(math.isfinite(y) and 0 <= y <= 110 for y in ir):
        raise ValueError('IR numerical data failed validation')
    def ms_at(x, y):
        return list(zip(struct.unpack_from('<54d', data, x), struct.unpack_from('<54d', data, y)))
    ms = ms_at(20849, 21285)
    if ms != ms_at(25461, 25897):
        raise ValueError('MS repeated data do not match')
    if not all(math.isfinite(x) and math.isfinite(y) and 0 <= y and 0 < x <= 156 for x, y in ms):
        raise ValueError('MS numerical data failed validation')
    if not all(ms[i][0] < ms[i + 1][0] for i in range(53)) or max(y for _, y in ms) != 6188:
        raise ValueError('MS peak table failed validation')
    return ir, ms


def export(source):
    source = Path(source)
    ir, ms = extract(source.read_bytes())  # verify before writing anything
    base = source.with_suffix('')
    ir_csv = base.with_name(base.name + '_IR.csv')
    ir_jdx = base.with_name(base.name + '_IR.jdx')
    ms_csv = base.with_name(base.name + '_MS.csv')
    ms_jdx = base.with_name(base.name + '_MS.jdx')
    with ir_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['wavenumber_cm-1', 'transmittance_percent'])
        w.writerows((4000 - i, format(y, '.12g')) for i, y in enumerate(ir))
    # X++(Y..Y) uses one starting X followed by several Y values per line.
    lines = [
        f'##TITLE={base.name} - IR', '##JCAMP-DX=5.00',
        '##DATA TYPE=INFRARED SPECTRUM', '##DATA CLASS=XYDATA',
        '##XUNITS=1/CM', '##YUNITS=TRANSMITTANCE',
        '##XFACTOR=1', '##YFACTOR=1', '##FIRSTX=4000',
        '##LASTX=450', '##NPOINTS=3551',
        f'##FIRSTY={ir[0]:.12g}', f'##MINY={min(ir):.12g}',
        f'##MAXY={max(ir):.12g}', '##DELTAX=-1',
        '##XYDATA=(X++(Y..Y))',
    ]
    for i in range(0, len(ir), 8):
        lines.append(f'{4000-i} ' + ' '.join(f'{y:.12g}' for y in ir[i:i+8]))
    lines.append('##END=')
    ir_jdx.write_text('\n'.join(lines) + '\n', encoding='ascii')
    max_intensity = max(y for _, y in ms)
    with ms_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['m_z', 'original_intensity', 'relative_abundance_percent'])
        w.writerows((f'{x:g}', f'{y:g}', f'{y/max_intensity*100:.9f}') for x, y in ms)
    lines = [
        f'##TITLE={base.name} - MS', '##JCAMP-DX=5.00',
        '##DATA TYPE=MASS SPECTRUM', '##DATA CLASS=PEAK TABLE',
        '##XUNITS=M/Z', '##YUNITS=RELATIVE ABUNDANCE',
        f'##FIRSTX={ms[0][0]:g}', f'##LASTX={ms[-1][0]:g}',
        f'##NPOINTS={len(ms)}', '##MINY=0', '##MAXY=100',
        '##PEAK TABLE=(XY..XY)',
    ]
    lines += [f'{x:g}, {y/max_intensity*100:.9f}' for x, y in ms]
    lines.append('##END=')
    ms_jdx.write_text('\n'.join(lines) + '\n', encoding='ascii')
    return [ir_csv, ir_jdx, ms_csv, ms_jdx]


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.title('MNOVA IR + MS to CSV / JDX')
    root.geometry('610x280')
    tk.Label(root, text='MNOVA → IR & MS converter', font=('Segoe UI', 16, 'bold')).pack(pady=(20, 8))
    tk.Label(root, text='Creates _IR.csv, _IR.jdx, _MS.csv, _MS.jdx beside the input file.').pack()
    tk.Label(root, text='Current version supports only the validated butanoic_acid.mnova sample.', fg='#a14b00').pack(pady=8)
    status = tk.StringVar(value='Choose an MNOVA file to begin.')
    tk.Label(root, textvariable=status, wraplength=570).pack(pady=12)
    def select():
        paths = filedialog.askopenfilenames(title='Select MNOVA file(s)', filetypes=[('MNOVA documents', '*.mnova'), ('All files', '*.*')])
        if not paths:
            return
        successes, failures = [], []
        for path in paths:
            try:
                outputs = export(path)
                successes.append(f'{Path(path).name}: ' + ', '.join(p.name for p in outputs))
            except Exception as exc:
                failures.append(f'{Path(path).name}: {exc}')
        status.set(f'Converted: {len(successes)} | Unsupported/failed: {len(failures)}')
        if successes:
            messagebox.showinfo('Conversion completed', '\n'.join(successes))
        if failures:
            messagebox.showwarning('Conversion not completed', '\n'.join(failures))
    tk.Button(root, text='Select MNOVA file(s) and convert', command=select, font=('Segoe UI', 12), padx=14, pady=9).pack(pady=8)
    root.mainloop()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        for name in sys.argv[1:]:
            try:
                for path in export(name):
                    print(path)
            except Exception as exc:
                print(f'ERROR: {name}: {exc}', file=sys.stderr)
                sys.exit(1)
    else:
        gui()
