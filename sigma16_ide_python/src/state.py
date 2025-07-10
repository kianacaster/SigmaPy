# state.py

# Copyright (C) 2024 John T. O'Donnell. License: GNU GPL Version 3
# See Sigma16/README, LICENSE, and https://jtod.github.io/home/Sigma16

# This file is part of Sigma16. Sigma16 is free software: you can
# redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
# Sigma16 is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details. You should have received
# a copy of the GNU General Public License along with Sigma16. If
# not, see <https://www.gnu.org/licenses/>.

# -------------------------------------------------------------------------
# state.py defines global state for the system, IDE, modules, and
# emulator, including key data structures.
# -------------------------------------------------------------------------

import re
import common
import arithmetic as arith
import architecture as arch
# import arrbuf # Will be ported later if needed

# -------------------------------------------------------------------------
# Stages
# -------------------------------------------------------------------------

StageAsm = "Asm"  # .asm.   assembly language source
StageObj = "Obj"  # .obj.   object code
StageOmd = "Omd"  # .omd.   metadata for obj
StageLnk = "Lnk"  # .lnk.   link command
StageExe = "Exe"  # .xmd.   metadata for exe
StageXmd = "Xmd"  # .xmd.   metadata for exe

def get_stage_sym(xs):
    if xs == "asm":
        return StageAsm
    elif xs == "obj":
        return StageObj
    elif xs == "omd":
        return StageOmd
    elif xs == "lnk":
        return StageLnk
    elif xs == "exe":
        return StageExe
    elif xs == "xmd":
        return StageXmd
    else:
        return None

# -------------------------------------------------------------------------
# System state
# -------------------------------------------------------------------------

class SystemState:
    def __init__(self):
        self.module_set = None
        self.emulator_state = None
        self.linker_state = None

# -------------------------------------------------------------------------
# Global state variable
# -------------------------------------------------------------------------

# The environment is a global variable that contains all the system
# state.

env = SystemState()

# -------------------------------------------------------------------------
# Module keys
# -------------------------------------------------------------------------

next_mod_key = 0
def new_mod_key():
    global next_mod_key
    i = next_mod_key
    next_mod_key += 1
    return i

# -------------------------------------------------------------------------
# Sigma16 module
# -------------------------------------------------------------------------

class Sigma16Module:
    def __init__(self, name, text):
        self.mod_key = new_mod_key()
        self.mod_idx = len(env.module_set.modules) # Transient array index
        self.module_name = name
        self.file_handle = None
        self.filename = "(no file)"
        self.file_record = None
        self.file_info = None
        self.file_type = "none"
        self.file_text = ""

        self.asm_src_code_origin = "none"
        self.current_asm_src = text
        self.asm_src_lines = text.split("\n")
        self.saved_asm_src = None
        self.asm_info = None

        self.obj_code_origin = "none"
        self.obj_md = None

        self.exe_code_origin = "none"
        self.exe_obj_md = None

    def ident(self):
        return f"module {self.mod_key}"

    # GUI-specific methods, will be implemented in PySide6 part
    def set_module_display(self):
        pass

    def stale_asm_code(self):
        pass

    def stale_obj_code(self):
        pass

    def stale_exe_code(self):
        pass

    def set_asm_code(self, txt, origin):
        self.asm_src_code_origin = origin
        self.current_asm_src = txt
        self.asm_src_lines = txt.split("\n")
        # GUI update logic will go here later

    def set_obj_code(self, txt, origin):
        self.obj_code_origin = origin
        self.current_obj_src = txt
        # GUI update logic will go here later

    def set_exe_code(self, txt, origin):
        self.exe_code_origin = origin
        self.current_exe_src = txt
        # GUI update logic will go here later

    def has_metadata(self):
        return self.md_text != ""

    def change_asm_src(self, txt):
        self.current_asm_src = txt
        # GUI update logic will go here later

    def change_saved_asm_src(self, txt):
        self.saved_asm_src = txt
        self.change_asm_src(txt)

    def set_selected(self, b):
        pass # GUI-specific

    def refresh_in_editor_buffer(self):
        pass # GUI-specific

    def show_short(self):
        xs = f"Sigma16Module key={self.mod_key} name={self.module_name}\n"
        xs += f" src={self.current_asm_src[:200]}...\n"
        if self.asm_info:
            xs += " AsmInfo:\n"
            xs += self.asm_info.show_short()
        xs += "End of module\n"
        return xs

# -------------------------------------------------------------------------
# Handle controls for individual modules (GUI-specific, omitted for now)
# -------------------------------------------------------------------------

def handle_select(m):
    pass

def handle_mod_up(m):
    pass

async def handle_mod_refresh(m):
    pass

def handle_close(m):
    pass

# -------------------------------------------------------------------------
# Sigma16 module set
# -------------------------------------------------------------------------

class ModuleSet:
    def __init__(self):
        common.mode.devlog("Initializing ModuleSet")
        self.modules = []
        self.selected_module_idx = 0
        self.previous_selected_idx = 0

    def add_module(self, name, text):
        m = Sigma16Module(name, text)
        self.modules.append(m)
        self.selected_module_idx = len(self.modules) - 1
        # GUI update logic will go here later
        return m

    def get_selected_module(self):
        return self.modules[self.selected_module_idx]

    def refresh_display(self):
        # GUI update logic will go here later
        pass

# ----------------------------------------------------------------------
# Assembler information record
# ----------------------------------------------------------------------

class AsmInfo:
    def __init__(self, base_name, src_text):
        self.asm_mod_name = base_name
        self.base_name = base_name
        self.asm_src_text = src_text
        self.asm_src_lines = src_text.split("\n")
        self.object_code = []
        self.object_text = ""
        self.md_text = ""
        self.metadata = Metadata()
        self.asm_listing_text = ""

        self.asm_stmt = []
        self.symbols = []
        self.symbol_table = {} # Using dict for Map
        self.location_counter = Value(0, Local, Relocatable)
        self.imports = []
        self.exports = []
        self.n_asm_errors = 0
        self.obj_md = None

    def show_short(self):
        xs = "AsmInfo\n"
        show_src = "\n".join(self.asm_src_lines[:4])
        show_obj = "\n".join(self.object_code[:4])
        xs += f" asm_mod_name={self.asm_mod_name}\n"
        xs += show_src + "\n"
        xs += show_obj + "\n"
        return xs

# ----------------------------------------------------------------------
# Symbol table
# ----------------------------------------------------------------------

class Identifier:
    def __init__(self, name, mod, extname, v, def_line):
        self.name = name
        self.mod = mod
        self.extname = extname
        self.value = v
        self.def_line = def_line
        self.usage_lines = []

    def __str__(self):
        return f"Identifier(name='{self.name}', value={self.value.to_string()})"

def display_symbol_table_html(ma):
    # This function is GUI-specific, will print to console for now
    print("\nSymbol table")
    print("Name        Val Org Mov  Def Used")
    
    syms = sorted(ma.symbol_table.keys())
    common.mode.devlog(f"Symbol table keys = {syms}")
    for symkey in syms:
        x = ma.symbol_table[symkey]
        fullname = f"{x.mod}.{x.name}" if x.mod else f"{x.name}"
        xs = f"{fullname.ljust(11)}{x.value.to_string()}{str(x.def_line).rjust(5)}  {','.join(map(str, x.usage_lines))}"
        print(xs)

# -------------------------------------------------------------------------
# Value
# -------------------------------------------------------------------------

# Origin attribute
Local = "Loc"         # defined in this module
External = "Ext"      # defined in another module

# Movability attribute
Fixed = "Fix"         # constant
Relocatable = "Rel"   # changes during relocation

class Value:
    def __init__(self, v, o, m):
        self.word = v
        self.origin = o
        self.movability = m

    def copy(self):
        return Value(self.word, self.origin, self.movability)

    def add(self, k):
        self.word = self.word + k.word
        if k.movability == Fixed:
            self.movability = self.movability
        elif self.movability == Fixed:
            self.movability = k.movability
        else:
            self.movability = Fixed # Both relocatable, result is fixed

    def to_string(self):
        xs = f"{arith.word_to_hex4(self.word)} {self.origin} {self.movability}"
        return xs

ExtVal = Value(0, External, Fixed)

def mk_const_val(k):
    return Value(k, Local, Fixed)

Zero = mk_const_val(0)
One = mk_const_val(1)
Two = mk_const_val(2)

# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

elts_per_line_limit = 4

class Metadata:
    def __init__(self):
        self.clear()

    def clear(self):
        self.pairs = []
        self.map_arr = {} # Using dict for mapArr
        self.listing_text = []
        self.listing_plain = []
        self.listing_dec = []
        self.md_text = None
        self.adr_offset = 0
        self.src_offset = 0

    def add_pairs(self, ps):
        for p in ps:
            self.map_arr[p["address"]] = p["index"]
            self.pairs.append(p)

    def translate_map(self, adr_offset, src_offset):
        self.adr_offset = adr_offset
        self.src_offset = src_offset
        xs = []
        self.map_arr = {}
        for x in self.pairs:
            p = {"address": x["address"] + adr_offset,
                 "index": x["index"] + src_offset}
            xs.append(p)
            self.map_arr[x["address"] + adr_offset] = x["index"] + src_offset
        self.pairs = xs

    def add_mapping_src(self, a, i, src_text, src_plain, src_dec):
        p = {"address": a, "index": i}
        self.pairs.append(p)
        self.map_arr[a] = i
        self.listing_text.append(src_text)
        self.listing_plain.append(src_plain)
        self.listing_dec.append(src_dec)

    def add_mapping(self, a, i):
        p = {"address": a, "index": i}
        self.pairs.append(p)
        self.map_arr[a] = i

    def push_src(self, src_text, src_plain, src_dec):
        self.listing_text.append(src_text)
        self.listing_plain.append(src_plain)
        self.listing_dec.append(src_dec)

    def unshift_src(self, src_text, src_plain, src_dec):
        self.listing_text.insert(0, src_text)
        self.listing_plain.insert(0, src_plain)
        self.listing_dec.insert(0, src_dec)

    def add_src(self, i, src_text, src_plain, src_dec):
        # Ensure lists are large enough
        while len(self.listing_text) <= i:
            self.listing_text.append("")
            self.listing_plain.append("")
            self.listing_dec.append("")
        self.listing_text[i] = src_text
        self.listing_plain[i] = src_plain
        self.listing_dec[i] = src_dec

    def get_src_idx(self, a):
        i = self.map_arr.get(a)
        return i if i is not None else 0

    def get_src_text(self, a):
        x = self.listing_text[self.get_src_idx(a)]
        return x if x is not None else f"no text src for {a}"

    def get_src_plain(self, a):
        x = self.listing_plain[self.get_src_idx(a)]
        return x if x is not None else f"no plain src for {a}"

    def get_src_dec(self, a):
        x = self.listing_dec[self.get_src_idx(a)]
        return x if x is not None else f"no decorated src for {a}"

    def get_md_text(self):
        if not self.md_text:
            self.md_text = self.to_text()
        return self.md_text

    def add_src_lines(self, xs):
        for i in range(0, len(xs), 3):
            self.listing_text.append(xs[i])
            self.listing_plain.append(xs[i+1])
            self.listing_dec.append(xs[i+2])

    def set_md_text(self, xs):
        self.md_text = xs

    def from_text(self, x):
        self.clear()
        self.md_text = x
        xs = x.split("\n")
        ns = []
        i = 0
        while i < len(xs) and not xs[i].startswith("source"):
            ys = xs[i].split(",")
            ns.extend([int(q) for q in ys if q.strip()]) # Ensure q is not empty
            i += 1
        
        j = 0
        while j < len(ns):
            a = ns[j] if ns[j] is not None else 0
            idx = ns[j+1] if ns[j+1] is not None else 0
            self.add_mapping(a, idx)
            j += 2
        
        i += 1 # skip "source"
        j = 0
        while i < len(xs):
            if xs[i] != "":
                self.listing_text.append(xs[i])
                self.listing_plain.append(xs[i+1])
                self.listing_dec.append(xs[i+2])
                j += 1
                i += 3
            else:
                i += 1 # skip empty line

    def map_to_texts(self):
        xs = []
        for p in self.pairs:
            xs.extend([p["address"], p["index"]])
        
        ys = []
        temp_xs = list(xs) # Create a mutable copy
        while len(temp_xs) > 0:
            ys.append(temp_xs[:elts_per_line_limit])
            temp_xs = temp_xs[elts_per_line_limit:]
        
        zs = []
        for y in ys:
            zs.append(",".join(map(str, y)))
        return zs

    def get_src_lines(self):
        xs = []
        for i in range(len(self.listing_plain)):
            xs.append(self.listing_text[i])
            xs.append(self.listing_plain[i])
            xs.append(self.listing_dec[i])
        return xs

    def get_plain_lines(self):
        return list(self.listing_plain)

    def to_text(self):
        xs = self.map_to_texts()
        xs.append("source")
        xs.extend(self.get_src_lines())
        return "\n".join(xs)

# -------------------------------------------------------------------------
# Imports and exports
# -------------------------------------------------------------------------

class AsmImport:
    def __init__(self, mod, name, addr, field):
        self.mod = mod
        self.name = name
        self.addr = addr
        self.field = field

    def show(self):
        return f"AsmImport mod={self.mod} name={self.name} " \
               f"addr={arith.word_to_hex4(self.addr)} field={self.field}\n"

def show_asm_imports(xs):
    r = "AsmImports...\n"
    for x in xs:
        r += x.show()
    return r

class AsmExport:
    def __init__(self, name, val, status):
        self.name = name
        self.val = val
        self.status = status

    def show(self):
        return f"Export name={self.name} val={arith.word_to_hex4(self.val)}" \
               f" status={self.status}"

def show_mod_map(m):
    r = "Module map...\n"
    for k in m.keys():
        r += f"key {k} -> {len(m[k].object_lines)}\n"
    return r

def show_asm_export_map(m):
    r = ""
    for k in m.keys():
        r += f"key {k} -> {m[k].show()}"
    return r

def show_asm_exports(xs):
    r = "AsmExports...\n"
    for x in xs:
        r += x.show()
    return r

def show_blocks(bs):
    xs = ""
    for b in bs:
        xs += b.show_block()
        print(b.xs)
    return xs

# -------------------------------------------------------------------------
# Container for object code and metadata
# -------------------------------------------------------------------------

class ObjMd:
    def __init__(self, mod_name, obj_text, md_text):
        self.mod_name = mod_name
        self.obj_text = obj_text
        self.obj_lines = obj_text.split("\n")
        self.md_text = md_text
        self.md_lines = md_text.split("\n") if md_text else []
        self.is_executable = self.check_executable()

    def check_executable(self):
        ok = True
        ok &= len(self.obj_lines) > 0
        for xs in self.obj_lines:
            fields = parse_obj_line(xs)
            if fields["operation"] == "import":
                common.mode.devlog(f"check executable: import ({fields['operands']})")
                print(f"check executable: import ({fields['operands']})")
                ok = False
        return ok

    def has_object_code(self):
        return bool(self.obj_text)

    def show_short(self):
        xs = "Object/Metadata:\n"
        xs += f"object module {self.mod_name} with " \
              f"{len(self.obj_lines)} lines of object text\n"
        xs += "\n".join(self.obj_lines[:3]) + "\n"
        xs += f"{len(self.md_lines)} lines of metadata text\n"
        xs += "\n".join(self.md_lines[:3])
        return xs

# -------------------------------------------------------------------------
# Object code parser
# -------------------------------------------------------------------------

def parse_obj_line(xs):
    obj_line_parser = re.compile(r"^([a-z]+)(?:\s+(.*))?$")
    blank_line_parser = re.compile(r"^\s*$")
    
    operation = ""
    operands = []
    
    blank_line_match = blank_line_parser.match(xs)
    split_line_match = obj_line_parser.match(xs)
    
    if split_line_match:
        operation = split_line_match.group(1)
        if split_line_match.group(2):
            operands = split_line_match.group(2).split(",")
    elif blank_line_match:
        pass # Blank line, do nothing
    else:
        print(f"linker error: object line has invalid format: {xs}")
    
    return {"operation": operation, "operands": operands}

# -------------------------------------------------------------------------
# Linker state
# -------------------------------------------------------------------------

class LinkerState:
    def __init__(self, main_name, obj_mds):
        self.main_name = main_name
        self.obj_mds = obj_mds
        self.mod_map = {} # Using dict for Map
        self.oi_list = []
        self.m_count = 0
        self.location_counter = 0
        self.metadata = Metadata()
        self.object_lines = []
        self.src_lines = []
        self.link_errors = []
        self.listing = ""
        self.exe_obj_md = None
        self.exe_code_text = "" # Added for consistency with JS
        self.exe_md_text = ""   # Added for consistency with JS

    def show_mod_map(self):
        print("Linker state modMap:")
        print(self.mod_map)
        print("End of modMap")

    def show(self):
        xs = "Linker state:\n"
        xs += f"Location counter = {arith.word_to_hex4(self.location_counter)}\n"
        xs += f"{len(self.link_errors)} Error messages: {self.link_errors}\n"
        xs += f"metadata.pairs.length = {len(self.metadata.pairs)}\n"
        xs += self.exe_code_text
        xs += self.exe_md_text
        return xs

# -------------------------------------------------------------------------
# Object Info
# -------------------------------------------------------------------------

def take_prefix(xs):
    return "\n".join(xs.split("\n")[:3]) if xs else xs

class ObjectInfo:
    def __init__(self, i, mod_name, obj_md):
        self.index = i
        self.mod_name = mod_name
        self.obj_md = obj_md
        self.obj_text = obj_md.obj_text
        self.md_text = obj_md.md_text
        self.object_lines = [] # Will be populated by parse_object
        self.md_lines = self.md_text.split("\n") if self.md_text else []
        self.metadata = None # Will be populated by parse_object
        self.start_address = 0
        self.src_line_origin = 0
        self.data_blocks = [ObjectBlock(0)]
        self.relocations = []
        self.asm_imports = []
        self.asm_export_map = {} # Using dict for Map
        self.om_asm_exports = []

    def show(self):
        # Simplified for console output
        xs = f"ObjectInfo for {self.mod_name}\n"
        xs += f"  Object lines: {len(self.object_lines)}\n"
        xs += f"  Start address: {arith.word_to_hex4(self.start_address)}\n"
        xs += f"  Relocations: {self.relocations}\n"
        xs += f"  Imports: {len(self.asm_imports)}\n"
        xs += f"  Exports: {len(self.asm_export_map)}\n"
        return xs

class ObjectBlock:
    def __init__(self, block_start):
        self.block_start = block_start
        self.block_size = 0
        self.xs = []

    def show_block(self):
        return f"Block of {self.block_size} words from " \
               f"{arith.word_to_hex4(self.block_start)}: " \
               f"{[arith.word_to_hex4(x) for x in self.xs]}"

    def insert_word(self, x):
        self.xs.append(x)
        self.block_size += 1

# Initialize the global module set
env.module_set = ModuleSet()
