"""Offline ELF comparison; never executes either binary."""
import struct,json,hashlib,sys
from pathlib import Path
original=Path(sys.argv[1]).read_bytes()
stripped=Path(sys.argv[2]).read_bytes()
def elf(data):
 assert data[:6]==b'\x7fELF\x02\x01'
 phoff,shoff=struct.unpack_from('<QQ',data,32)
 phsize,phnum,shsize,shnum,shidx=struct.unpack_from('<HHHHH',data,54)
 ph=[struct.unpack_from('<IIQQQQQQ',data,phoff+i*phsize) for i in range(phnum)]
 sh=[struct.unpack_from('<IIQQQQIIQQ',data,shoff+i*shsize) for i in range(shnum)]
 st=sh[shidx];names=data[st[4]:st[4]+st[5]]
 sections={names[x[0]:].split(b'\0')[0].decode():x for x in sh}
 return ph,sections
pa,sa=elf(original);pb,sb=elf(stripped)
assert pa==pb,'program headers changed'
assert original[:40]==stripped[:40] and original[48:58]==stripped[48:58],'execution ELF header changed'
load=[]
for i,p in enumerate(pa):
 if p[0]!=1:continue
 old=bytearray(original[p[2]:p[2]+p[5]]);new=bytearray(stripped[p[2]:p[2]+p[5]])
 # Only section-table pointer/count metadata in ELF header may differ.
 for x,y in [(40,48),(58,64)]:
  if p[2]<=x and y<=p[2]+p[5]:old[x-p[2]:y-p[2]]=new[x-p[2]:y-p[2]]=b'\0'*(y-x)
 assert old==new,('PT_LOAD changed',i)
 load.append(i)
alloc=[]
for name,s in sa.items():
 if not s[2]&2:continue
 n=sb[name]
 assert s[1:8]==n[1:8],('allocated section metadata',name)
 if s[1]!=8:assert original[s[4]:s[4]+s[5]]==stripped[n[4]:n[4]+n[5]],name
 alloc.append(name)
assert '.symtab' not in sb and '.strtab' not in sb
assert '.dynsym' in sb and '.dynstr' in sb
assert not any(n.startswith('.debug') for n in sb)
print(json.dumps({"program_headers_identical":True,"load_segments_identical_except_section_table_metadata":load,"allocated_sections_identical":alloc,"removed_sections":sorted(set(sa)-set(sb))},indent=2))
