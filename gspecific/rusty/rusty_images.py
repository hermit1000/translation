#!/usr/bin/env python3
"""Self-contained Rusty PC-98 LZ/MAG/MGX image codec."""
from __future__ import annotations
import json, struct
from pathlib import Path
from PIL import Image

MAGIC=b"MAKI02A \x1a"; LZ_MAGIC=b"LZ\x1a"
MGX_DISPLACEMENTS=(0x59E,0x5A0,0x5A2,0x5A6,0x99E,0x9A0,0xD9E,0xDA0,0xDA2,0x159E,0x15A0,0x15A2,0x259E,0x25A0,0x25A2,0x459E)
DX=(0,1,2,4,0,1,0,1,2,0,1,2,0,1,2,0); DY=(0,0,0,0,1,1,2,2,2,4,4,4,8,8,8,16)

def rusty_lz_decode(data:bytes)->bytes:
    if not data.startswith(LZ_MAGIC): return data
    if len(data)<7: raise ValueError("truncated Rusty LZ header")
    expected=struct.unpack_from('<I',data,3)[0]; src=7; flags=0; ring=bytearray(4096); rp=0xFEE; out=bytearray()
    while src<len(data) and len(out)<expected:
        flags >>= 1
        if not (flags & 0x100):
            if src>=len(data): break
            flags=data[src] | 0xff00; src+=1
        if flags&1:
            v=data[src]; src+=1; out.append(v); ring[rp]=v; rp=(rp+1)&0xfff
        else:
            if src+1>=len(data): break
            match=data[src] | ((data[src+1]&0xf0)<<4); count=(data[src+1]&15)+3; src+=2; pos=match
            for _ in range(count):
                v=ring[pos]; pos=(pos+1)&0xfff; out.append(v); ring[rp]=v; rp=(rp+1)&0xfff
                if len(out)>=expected: break
    if len(out)!=expected: raise ValueError(f"Rusty LZ stream ended early ({len(out)}/{expected})")
    return bytes(out)

def _sub290_planes(a,b):
    ax=a&0xffff; bx=b&0xffff; bp=ax; dx=ax; dx=(dx<<4)&0xffff; bx=(bx>>4)&0xffff
    bp&=0xf0f0; dx&=0xf0f0; ax&=0x0f0f; bx&=0x0f0f; bx|=bp; dx|=ax
    return dx&255,bx&255,(dx>>8)&255,(bx>>8)&255

def read_mgx_header(data):
    if not data.startswith(MAGIC): raise ValueError("not a Rusty MAKI02A MGX file")
    h=9; x0,y0,x1,y1=struct.unpack_from('<HHHH',data,h+4); fa,fb,fbs,color,colors=struct.unpack_from('<IIIII',data,h+12); pal=[]
    for i in range(16):
        g,r,b=data[h+32+i*3:h+35+i*3]; pal.append((r&15,g&15,b&15))
    return {'header':h,'x0':x0,'y0':y0,'x1':x1,'y1':y1,'flag_a':fa,'flag_b':fb,'flag_b_size':fbs,'color':color,'color_size':colors,'palette_4bit':pal}

def _looks_like_nibble_pixels(words):
    s=words[:min(len(words),256)]
    repeated=sum((w&0xffff)==(w&15)*0x1111 for w in s)
    return bool(s) and repeated*100>=len(s)*95

def decode(source:Path,target:Path,meta_path=None,word_dump=None,trace_path=None):
    data=rusty_lz_decode(Path(source).read_bytes()); m=read_mgx_header(data); h=m['header']; left=m['x0']&-4; right=(m['x1']+4)&-4; sw=right-left; w=m['x1']-m['x0']+1; hh=m['y1']-m['y0']+1; wr=sw//4; count=wr*hh
    fa0=h+m['flag_a']; fb0=h+m['flag_b']; co0=h+m['color']; fa=data[fa0:fb0]; fb=data[fb0:fb0+m['flag_b_size']]; cs=data[co0:co0+m['color_size']]
    act=bytearray(max(1,sw//8)); out=[]; trace=[]; ring=bytearray(17824); base=bc=cc=fi=0; fm=128
    def color():
        nonlocal cc
        if cc+2>len(cs): raise ValueError('color stream ended before the pixel stream')
        v=struct.unpack_from('<H',cs,cc)[0]; cc+=2; return v
    def readrel(r):
        r=(r&0x3fff)+0x59e; return ring[r]|ring[r+1]<<8
    def writerel(r,v): ring[r]=v&255; ring[r+1]=(v>>8)&255
    for row in range(hh):
        for j in range(len(act)):
            if fi>=len(fa): raise ValueError('Flag-A stream ended before the pixel stream')
            if not fa[fi]&fm:
                if bc>=len(fb): raise ValueError('Flag-B stream ended before the pixel stream')
                act[j]^=fb[bc]; bc+=1
            fm>>=1
            if not fm: fm=128; fi+=1
        for j,v in enumerate(act):
            di=base+0x59e+j*4
            for code,extra in ((v>>4,0),(v&15,2)):
                value=color() if code==0 else readrel(di-MGX_DISPLACEMENTS[code]+extra); writerel(di+extra,value); out.append(value)
                if trace_path is not None: trace.append({'row':row,'action':j,'nibble':code,'literal':code==0,'word':value})
        base=(base+1024)&0x3fff
    if len(out)<count: raise ValueError(f'pixel stream ended early ({len(out)}/{count} words)')
    if word_dump: Path(word_dump).parent.mkdir(parents=True,exist_ok=True); Path(word_dump).write_bytes(b''.join(struct.pack('<H',v) for v in out[:count]))
    if trace_path: Path(trace_path).parent.mkdir(parents=True,exist_ok=True); Path(trace_path).write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pal=[(r*17,g*17,b*17,255) for r,g,b in m['palette_4bit']]; pixels=[]; crop=m['x0']-left; nib=_looks_like_nibble_pixels(out)
    for y in range(hh):
        row=out[y*wr:(y+1)*wr]; expanded=[]
        if nib:
            for v in row:
                for bit in range(3,-1,-1): expanded.append(pal[15] if (v&15)>>bit&1 else pal[0])
        else:
            for i in range(0,len(row),2):
                planes=_sub290_planes(row[i],row[i+1])
                for bit in range(7,-1,-1): expanded.append(pal[sum(((p>>bit)&1)<<j for j,p in enumerate(planes))])
        pixels.extend(expanded[crop:crop+w])
    im=Image.new('RGBA',(w,hh)); im.putdata(pixels); Path(target).parent.mkdir(parents=True,exist_ok=True); im.save(target)
    result={'format':'Rusty-MGX','source':Path(source).name,'x':m['x0'],'y':m['y0'],'width':w,'height':hh,'x1':m['x1'],'y1':m['y1'],'palette_4bit_rgb':[list(c) for c in m['palette_4bit']],'pixel_mode':'nibble-bitmask' if nib else 'four-plane'}
    if meta_path: Path(meta_path).parent.mkdir(parents=True,exist_ok=True); Path(meta_path).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

decode_mgx=decode

def _palette_for(im):
    colors=im.convert('RGB').getcolors(maxcolors=1<<20) or []; pal=[c for _,c in sorted(colors,reverse=True)[:16]]
    while len(pal)<16: pal.append((0,0,0))
    return pal,{c:i for i,c in enumerate(pal)}

def encode(source:Path,target:Path,x=0,y=0):
    im=Image.open(source).convert('RGB'); w,hh=im.size; x0=x; x1=x+w-1; left=x0&-4; action_len=(x1//8)-(x0//8)+1; sw=action_len*8; pal,lookup=_palette_for(im)
    pixels=list(im.getdata()); bw=all(max(rgb)-min(rgb)<4 for rgb in pixels); words=[]
    for yy in range(hh):
        for xx in range(0,sw,4):
            if bw:
                mask=0
                for p in range(4):
                    rgb=im.getpixel((min(max(xx+p-(x0-left),0),w-1),yy)); mask=(mask<<1)|(1 if sum(rgb)//3>127 else 0)
                v=mask*0x1111
            else:
                v=0
                for p in range(4): v=(v<<4)|lookup.get(im.getpixel((min(max(xx+p-(x0-left),0),w-1),yy)),0)
            words.append(v)
    fas=(hh*(sw//8)+7)//8; fa=bytes([255])*fas; fo=0x50; fb=fo+fas; co=fb; out=bytearray(MAGIC+b'\0\0\0\0')+struct.pack('<HHHH',x0,y,x1,y+hh-1)+struct.pack('<IIIII',fo,fb,0,co,len(words)*2)
    if bw: pal=[(0,0,0)]+[(0,0,0)]*14+[(255,255,255)]
    # MGX palette stores each 4-bit component in both nibbles (00/77/FF).
    for r,g,b in pal: out+=bytes((((g//17)&15)*0x11,((r//17)&15)*0x11,((b//17)&15)*0x11))
    out+=fa+b''.join(struct.pack('<H',v) for v in words); Path(target).parent.mkdir(parents=True,exist_ok=True); Path(target).write_bytes(out)
    return {'format':'Rusty-MGX','source':Path(source).name,'width':w,'height':hh,'x':x,'y':y}

encode_mgx=encode

def decode_mag(source:Path,target:Path):
    data=rusty_lz_decode(Path(source).read_bytes()); p=data.find(b'MAKI02');
    if p<0: raise ValueError('MAKI02 signature not found')
    h=data.find(b'\x1a',p+6)+1; x0,y0,x1,y1=struct.unpack_from('<HHHH',data,h+4); fa,fb,fbs,co,csz=struct.unpack_from('<IIIII',data,h+12); x0&=-8; x1|=7; sw=x1-x0+1; hh=y1-y0+1; pal=[]
    for i in range(16): g,r,b=data[h+32+i*3:h+35+i*3]; pal.append((r*17,g*17,b*17,255))
    actions=bytearray(sw//8); aa=data[h+fa:h+fb]; bb=data[h+fb:h+fb+fbs]; cc=data[h+co:h+co+csz]; out=[]; ai=-1; bi=ci=0; mask=128; target_words=(sw//4)*hh
    for flag in aa:
        for bit in (128,64,32,16,8,4,2,1):
            if len(out)>=target_words: break
            nxt=(ai+1)%len(actions)
            if flag&bit:
                if bi>=len(bb): raise ValueError('MAG Flag-B stream ended')
                actions[nxt]^=bb[bi]; bi+=1
            ai=nxt
            for n in (actions[ai]>>4,actions[ai]&15):
                if len(out)>=target_words: break
                if n==0:
                    if ci+2>len(cc): raise ValueError('MAG color stream ended')
                    z=struct.unpack_from('>H',cc,ci)[0]; ci+=2
                else:
                    src=len(out)-DX[n]-sw//4*DY[n]
                    if src<0: raise ValueError('invalid MAG back-reference')
                    z=out[src]
                out.append(z)
    pix=[]
    for z in out:
        for sh in (12,8,4,0): pix.append(pal[z>>sh&15])
    im=Image.new('RGBA',(sw,hh)); im.putdata(pix[:sw*hh]); Path(target).parent.mkdir(parents=True,exist_ok=True); im.save(target)
    return {'format':'Rusty-MAG','source':Path(source).name,'width':sw,'height':hh,'x':x0,'y':y0,'x1':x1,'y1':y1,'pixel_mode':'four-color-nibble'}

def encode_mag(source:Path,target:Path):
    im=Image.open(source).convert('RGB'); w,hh=im.size; sw=(w+7)&-8; pal,lookup=_palette_for(im); fa=bytes([255])*((sw//8+7)//8*hh); words=[]
    for yy in range(hh):
        for xx in range(0,sw,4):
            v=0
            for p in range(4): v=(v<<4)|lookup.get(im.getpixel((min(xx+p,w-1),yy)),0)
            words.append(v)
    fo=0x50; fb=fo+len(fa); co=fb; out=bytearray(b'MAKI02A \x1a\0\0\0\0')+struct.pack('<HHHH',0,0,sw-1,hh-1)+struct.pack('<IIIII',fo,fb,0,co,len(words)*2)
    for r,g,b in pal: out+=bytes((((g//17)&15)*0x11,((r//17)&15)*0x11,((b//17)&15)*0x11))
    out+=fa+b''.join(struct.pack('>H',v) for v in words); Path(target).parent.mkdir(parents=True,exist_ok=True); Path(target).write_bytes(out)
    return {'format':'Rusty-MAG','source':Path(source).name,'width':w,'height':hh}

__all__=['decode_mag','decode_mgx','encode_mag','encode_mgx','read_mgx_header','rusty_lz_decode']
