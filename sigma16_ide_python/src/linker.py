# linker.py

# Copyright (c) 2024 John T. O'Donnell. License: GNU GPL Version 3
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
# linker.py manipulates object code, including the functions of a
# linker and loader. Services include combining a collection of
# object modules to form an executable module; performing address
# relocation; and loading an object module into memory.
# -------------------------------------------------------------------------

import common
import s16module as smod
import architecture as arch
import arithmetic as arith
import state as st
import assembler as asm # Import assembler for parse_obj_line

# ------------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------------

def adjust(ls, om, addr, f):
    found = False
    for b in om.data_blocks:
        if b.block_start <= addr < b.block_start + b.block_size:
            x = b.xs[addr - b.block_start]
            y = f(x)
            print(f"    Adjusting block {om.data_blocks.index(b)}" \
                  f" start={arith.word_to_hex4(b.block_start)}" \
                  f" size={b.block_size}" \
                  f" addr={arith.word_to_hex4(addr)}" \
                  f" old={arith.word_to_hex4(x)}" \
                  f" new={arith.word_to_hex4(y)}")
            b.xs[addr - b.block_start] = y
            found = True
            break
    if not found:
        print(f"Linker error: address {arith.word_to_hex4(addr)} not defined")

# ------------------------------------------------------------------------
# GUI interface to linker (placeholders for now)
# ------------------------------------------------------------------------

def linker_gui():
    print("linker_gui: GUI function, not implemented in CLI")

def link_show_object():
    print("link_show_object: GUI function, not implemented in CLI")

def link_show_executable():
    print("link_show_executable: GUI function, not implemented in CLI")

def link_show_metadata():
    print("link_show_metadata: GUI function, not implemented in CLI")

# -------------------------------------------------------------------------
# Linker main interface
# -------------------------------------------------------------------------

def linker(main_name, obj_mds):
    main_name = "Executable"  # Use main prog module name?
    print(f"Entering linker, main module = {main_name}")
    ls = st.LinkerState(main_name, obj_mds)
    st.env.linker_state = ls  # record linker state in global environment
    pass1(ls)  # parse object and record directives
    pass2(ls)  # process imports and relocations
    ls.exe_code_text = emit_code(ls)
    ls.exe_md_text = ls.metadata.to_text()
    ls.exe_obj_md = None if len(ls.link_errors) > 0 else st.ObjMd("executable", ls.exe_code_text, ls.exe_md_text)
    print(f"Number of linker errors = {len(ls.link_errors)}")
    print(f"Linker errors = {ls.link_errors}")
    return ls

# -------------------------------------------------------------------------
# Linker pass 1
# -------------------------------------------------------------------------

def pass1(ls):
    print("*** Linker pass 1")
    ls.m_count = 0
    ls.oi_list = []
    for obj_md in ls.obj_mds:
        print(f"Linker pass 1: i={ls.m_count} examining {obj_md.mod_name}")
        oi = st.ObjectInfo(ls.m_count, obj_md.mod_name, obj_md)
        ls.mod_map[oi.mod_name] = oi
        ls.oi_list.append(oi)
        oi.object_lines = obj_md.obj_text.split("\n")
        oi.metadata = st.Metadata()
        oi.metadata.from_text(oi.md_text)
        oi.start_address = ls.location_counter
        oi.src_line_origin = len(ls.metadata.get_plain_lines())
        ls.metadata.add_src_lines(oi.metadata.get_src_lines())
        parse_object(ls, oi)
        oi.metadata.translate_map(oi.start_address, oi.src_line_origin)
        ls.metadata.add_pairs(oi.metadata.pairs)
        ls.m_count += 1
    print("Linker pass1 finished")
    ls.show_mod_map()

def parse_object(ls, obj):
    common.mode.trace = False
    obj.start_address = ls.location_counter
    ls.mod_map[obj.mod_name] = obj
    obj.asm_export_map = {}
    rel_k = obj.start_address

    for x in obj.object_lines:
        fields = asm.parse_obj_line(x) # Use assembler's parse_obj_line
        common.mode.devlog(f"--op={fields["operation"]} args={fields["operands"]}")
        if not x.strip(): # Check for empty or whitespace-only lines
            pass
        elif fields["operation"] == "module":
            obj.dclmodname = fields["operands"][0]
            common.mode.devlog(f"  Module name: {obj.dclmodname}")
        elif fields["operation"] == "data":
            common.mode.devlog("-- data")
            for val_str in fields["operands"]:
                val = arith.hex4_to_word(val_str)
                safe_val = val if not arith.is_nan(val) else 0
                common.mode.devlog(f"  {arith.word_to_hex4(ls.location_counter)} " \
                                 f"{arith.word_to_hex4(safe_val)}")
                obj.data_blocks[-1].insert_word(safe_val)
                ls.location_counter += 1
        elif fields["operation"] == "import":
            obj.asm_imports.append(st.AsmImport(*fields["operands"]))
        elif fields["operation"] == "export":
            name, val, status = fields["operands"]
            val_num = arith.hex4_to_word(val)
            val_exp = val_num + rel_k if status == "relocatable" else val_num
            x = st.AsmExport(name, val_exp, status)
            obj.asm_export_map[name] = x
        elif fields["operation"] == "relocate":
            obj.relocations.extend(fields["operands"])
        else:
            common.mode.devlog(f">>> Syntax error ({fields["operation"]})")

# -------------------------------------------------------------------------
# Linker pass 2
# -------------------------------------------------------------------------

def pass2(ls):
    print("Linker Pass 2")
    for oi in ls.oi_list:
        print(f"--- pass 2 oi {oi.index} ({oi.mod_name})")
        resolve_imports(ls, oi)
        resolve_relocations(ls, oi)

def resolve_imports(ls, om):
    print(f"Resolving imports for {om.mod_name}")
    for x in om.asm_imports:
        if x.mod in ls.mod_map:  # does import module exist?
            exporter = ls.mod_map[x.mod]
            if x.name in exporter.asm_export_map:  # is name exported?
                v = exporter.asm_export_map[x.name]
                addr_num = arith.hex4_to_word(x.addr)
                val_num = v.val
                adjust(ls, om, addr_num, lambda y: val_num)
            else:
                print(f"Linker error: {x.name} not exported by {x.mod}")
        else:
            print(f"Linker error: {x.mod} not found")

def resolve_relocations(ls, om):
    rel_k = om.start_address
    print(f"Resolving relocations for {om.mod_name} relocation={arith.word_to_hex4(rel_k)}")
    for a in om.relocations:
        print(f"  relocate {arith.word_to_hex4(arith.hex4_to_word(a))}")
        address_num = arith.hex4_to_word(a)
        adjust(ls, om, address_num, lambda y: y + rel_k)

# -------------------------------------------------------------------------
# Emit object code
# -------------------------------------------------------------------------

def emit_code(ls):
    print("Emit object code")
    exe_code = ""
    if len(ls.link_errors) > 0:
        print("Link errors, cannot emit code")
    else:
        for oi in ls.oi_list:
            print(f"Emitting code for {oi.mod_name}")
            exe_code += f"module {oi.mod_name}\n"
            exe_code += f"org {arith.word_to_hex4(oi.start_address)}\n"
            for b in oi.data_blocks:
                exe_code += emit_object_words(b.xs)
        print("Executable code:")
        print(exe_code)
    return exe_code

obj_buffer_limit = 8

def emit_object_words(ws):
    code = ""
    temp_ws = list(ws) # Create a mutable copy
    while temp_ws:
        xs = temp_ws[:obj_buffer_limit]
        temp_ws = temp_ws[obj_buffer_limit:]
        ys = [arith.word_to_hex4(w) for w in xs]
        zs = 'data ' + ','.join(ys) + "\n"
        code += zs
    return code
