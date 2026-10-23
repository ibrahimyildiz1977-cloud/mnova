#!/usr/bin/env python3
"""Experimental MNOVA IR/MS extractor, tested with butanoic acid and 1-butanol.
Uses verified structural signatures, never synthesizes spectra.
"""
import csv, math, re, struct, sys
from pathlib import Path

def extract(data):
    if not data.startswith(b'Mestrelab Research S.L.'):
        raise ValueError('Not a recognized Mestrelab document')
    # The axis descriptor is a stable UTF-16LE marker in both tested documents.
    anchor = data.find('Wavenumber'.encode('utf-16le'))
    if anchor < 0:
        raise ValueError('IR wavenumber metadata not found')
    ir_offset = anchor + 1159
    n_ir = 3551  # confirmed 4000..450, step -1, in both tested documents
    ir = struct.unpack_from('>'+str(n_ir)+'d', data, ir_offset)
    ir_bytes = data[ir_offset:ir_offset+n_ir*8]
    if (not all(math.isfinite(v) and 0<=v<=110 for v in ir)
            or data.find(ir_bytes,ir_offset+n_ir*8) < 0):
        raise ValueError('IR arrays did not pass numerical/duplicate verification')
    # MS peak count and bounds are read from embedded UTF-16LE JCAMP metadata.
    marker = 'datatype=mass spectrum'.encode('utf-16le')
    pos = data.find(marker)
    if pos < 0:
        raise ValueError('MS metadata not found')
    header = data[pos:pos+2500].decode('utf-16le',errors='ignore')
    def field(key):
        m = re.search(r'(?:^|\n)'+re.escape(key)+r'=([^\n\r]+)',header)
        if not m: raise ValueError('MS metadata field missing: '+key)
        return float(m.group(1).strip())
    n = int(field('npoints')); first=field('firstx'); last=field('lastx'); peakmax=field('maxy')
    if not (1 <= n <= 50000): raise ValueError('Invalid MS peak count')
    matches=[]
    for o in range(max(0,pos-5000),min(len(data)-16*n,pos+12000)):
        if data[o:o+8] != struct.pack('<d',first): continue
        x=struct.unpack_from('<'+str(n)+'d',data,o)
        if x[-1]!=last or not all(math.isfinite(v) and v>0 for v in x) or not all(x[i]<x[i+1] for i in range(n-1)):
            continue
        y=struct.unpack_from('<'+str(n)+'d',data,o+8*n+4) if False else None
        # Data arrays are separated by a four-byte header in the tested files.
        # Check several small alignment offsets instead of assuming one.
        for gap in (4,0,8,12,16):
            yo=o+8*n+gap
            y=struct.unpack_from('<'+str(n)+'d',data,yo)
            if all(math.isfinite(v) and v>=0 for v in y) and abs(max(y)-peakmax)<max(1e-4,peakmax*1e-7):
                matches.append((o,gap,list(zip(x,y))))
    if not matches: raise ValueError('MS arrays did not match metadata')
    return ir,matches[0][2]

def export(filename):
    source=Path(filename); ir,ms=extract(source.read_bytes()); stem=source.with_suffix('')
    outputs=[stem.with_name(stem.name+'_'+kind+'.'+ext) for kind in ('IR','MS') for ext in ('csv','jdx')]
    ircsv,irjdx,mscsv,msjdx=outputs
    with ircsv.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['wavenumber_cm-1','transmittance_percent']);w.writerows((4000-i,format(y,'.12g')) for i,y in enumerate(ir))
    lines=[f'##TITLE={stem.name} IR','##JCAMP-DX=5.00','##DATA TYPE=INFRARED SPECTRUM','##DATA CLASS=XYDATA','##XUNITS=1/CM','##YUNITS=TRANSMITTANCE','##XFACTOR=1','##YFACTOR=1','##FIRSTX=4000','##LASTX=450','##NPOINTS=3551','##DELTAX=-1','##XYDATA=(X++(Y..Y))']
    for i in range(0,len(ir),8):lines.append(str(4000-i)+' '+' '.join(format(v,'.12g') for v in ir[i:i+8]))
    irjdx.write_text('\n'.join(lines+['##END=','']),encoding='ascii')
    peakmax=max(y for x,y in ms)
    with mscsv.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['m_z','original_intensity','relative_abundance_percent']);w.writerows((format(x,'g'),format(y,'g'),format(100*y/peakmax,'.9f')) for x,y in ms)
    lines=[f'##TITLE={stem.name} MS','##JCAMP-DX=5.00','##DATA TYPE=MASS SPECTRUM','##DATA CLASS=PEAK TABLE','##XUNITS=M/Z','##YUNITS=RELATIVE ABUNDANCE',f'##FIRSTX={ms[0][0]:g}',f'##LASTX={ms[-1][0]:g}',f'##NPOINTS={len(ms)}','##PEAK TABLE=(XY..XY)']
    lines += [f'{x:g}, {100*y/peakmax:.9f}' for x,y in ms]
    msjdx.write_text('\n'.join(lines+['##END=','']),encoding='ascii')
    return outputs

def main():
    if len(sys.argv)>1: paths=sys.argv[1:]
    else:
        import tkinter as tk
        from tkinter import filedialog,messagebox
        root=tk.Tk();root.withdraw()
        paths=filedialog.askopenfilenames(title='Choose MNOVA files',filetypes=[('MNOVA','*.mnova')])
        if not paths:return
    results=[]
    for path in paths:
        try: results.append('Converted '+Path(path).name+'\n'+'\n'.join(str(p) for p in export(path)))
        except Exception as exc:results.append('Could not convert '+Path(path).name+': '+str(exc))
    msg='\n\n'.join(results)
    print(msg)
    if len(sys.argv)==1:
        messagebox.showinfo('MNOVA conversion',msg)
if __name__=='__main__':main()
