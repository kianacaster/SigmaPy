# s16module.py

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

# --------------------------------------------------------------------------
# s16module.py: represent S16 module and set of modules, handle files
# --------------------------------------------------------------------------

import common
import state as st
# import assembler as asm # Will be imported when needed

# --------------------------------------------------------------------------
# File handling utilities
# --------------------------------------------------------------------------

def get_file_base_name(fname):
    i = fname.find(".")
    if i != -1:
        return fname[:i]
    return fname

def get_file_extension(fname):
    i = fname.find(".")
    if i != -1:
        return fname[i:]
    return ""

# --------------------------------------------------------------------------
# Sigma16 Module (moved from state.py for better organization)
# --------------------------------------------------------------------------

class Sigma16Module:
    def __init__(self, name, text):
        self.mod_key = st.new_mod_key()
        self.mod_idx = len(st.env.module_set.modules) if st.env.module_set else 0
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

    # GUI-specific methods (placeholders for now)
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
        # GUI update logic here later

    def set_obj_code(self, txt, origin):
        self.obj_code_origin = origin
        self.current_obj_src = txt
        # GUI update logic here later

    def set_exe_code(self, txt, origin):
        self.exe_code_origin = origin
        self.current_exe_src = txt
        # GUI update logic here later

    def has_metadata(self):
        return self.md_text != ""

    def change_asm_src(self, txt):
        self.current_asm_src = txt
        # GUI update logic here later

    def change_saved_asm_src(self, txt):
        self.saved_asm_src = txt
        self.change_asm_src(txt)

    def set_selected(self, b):
        pass  # GUI-specific

    def refresh_in_editor_buffer(self):
        pass  # GUI-specific

    def show_short(self):
        xs = f"Sigma16Module key={self.mod_key} name={self.module_name}\n"
        xs += f" src={self.current_asm_src[:200]}...\n"
        if self.asm_info:
            xs += " AsmInfo:\n"
            xs += self.asm_info.show_short()
        xs += "End of module\n"
        return xs

# --------------------------------------------------------------------------
# Sigma16 module set (moved from state.py for better organization)
# --------------------------------------------------------------------------

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
        # GUI update logic here later
        return m

    def get_selected_module(self):
        if not self.modules:
            return None # Or raise an error, depending on desired behavior
        return self.modules[self.selected_module_idx]

    def refresh_display(self):
        # GUI update logic here later
        pass

# Re-assign env.module_set to the new ModuleSet class
st.env.module_set = ModuleSet()

# --------------------------------------------------------------------------
# File handling functions (placeholders for now)
# --------------------------------------------------------------------------

async def open_file():
    print("open_file: Not implemented for CLI")

async def refresh_file():
    print("refresh_file: Not implemented for CLI")

async def save_file():
    print("save_file: Not implemented for CLI")

async def save_as_file():
    print("save_as_file: Not implemented for CLI")

async def open_directory():
    print("open_directory: Not implemented for CLI")

# --------------------------------------------------------------------------
# GUI-related handlers (placeholders for now)
# --------------------------------------------------------------------------

def handle_select(m):
    print(f"handle_select: Module {m.module_name} selected")
    # GUI-specific logic to update selected module display
    if st.env.module_set:
        old_sel_idx = st.env.module_set.selected_module_idx
        new_sel_idx = m.mod_idx
        if old_sel_idx < len(st.env.module_set.modules):
            st.env.module_set.modules[old_sel_idx].set_selected(False)
        st.env.module_set.modules[new_sel_idx].set_selected(True)
        st.env.module_set.selected_module_idx = new_sel_idx
        st.env.module_set.previous_selected_idx = old_sel_idx

def handle_mod_up(m):
    print(f"handle_mod_up: Module {m.module_name} moved up")
    # GUI-specific logic to reorder modules

async def handle_mod_refresh(m):
    print(f"handle_mod_refresh: Module {m.module_name} refreshed")
    # GUI-specific logic to refresh module content from file

def handle_close(m):
    print(f"handle_close: Module {m.module_name} closed")
    # GUI-specific logic to remove module from display and list
    if st.env.module_set:
        i = m.mod_idx
        a = st.env.module_set.modules

        si = st.env.module_set.selected_module_idx
        pi = st.env.module_set.previous_selected_idx

        if si == i:
            si = max(0, si - 1)
        elif si > i:
            si -= 1
        
        if pi == i:
            pi = 0
        elif pi > i:
            pi -= 1

        st.env.module_set.selected_module_idx = si
        st.env.module_set.previous_selected_idx = pi

        a.pop(i)
        for j in range(i, len(a)):
            a[j].mod_idx = j

# --------------------------------------------------------------------------
# FileRecord and related functions (legacy, may not be fully ported)
# --------------------------------------------------------------------------

class FileRecord:
    def __init__(self, f, base_name, stage):
        self.f = f
        self.file_name = f.name
        self.base_name = base_name
        self.stage = stage
        self.text = ""
        self.file_reader = None # mk_file_reader(self)
        self.file_read_complete = False

def check_file_name(xs):
    components = xs.split(".")
    errors = []
    base_name = None
    stage = st.StageExe

    if len(components) != 3:
        errors.append(f"Filename {xs} must have three components, e.g. ProgramName.asm.txt")
    elif components[2] != "txt":
        errors.append(f"Last component of filename {xs} is {components[2]} but it must be \".txt\"")
    elif components[1] not in ["asm", "obj", "lst", "omd", "lnk", "exe", "xmd"]:
        errors.append(f"Second component of filename {xs} is {components[1]} but it must be one of asm,obj,md,lnk")
    else:
        base_name = components[0]
        stage = st.get_stage_sym(components[1])
    
    result = {"errors": errors, "base_name": base_name, "stage": stage}
    common.mode.devlog(f"check_file_name {xs}\n errors={result['errors']} base_name={result['base_name']} stage={result['stage']}")
    return result

# Placeholder for handle_selected_files and mk_file_reader
# These are heavily tied to browser APIs and will be re-implemented with PySide6 file dialogs.

def handle_selected_files(flist):
    print("handle_selected_files: Not implemented for CLI")

def mk_file_reader(file_record):
    print("mk_file_reader: Not implemented for CLI")
    return None

def refresh_when_reads_finished():
    print("refresh_when_reads_finished: Not implemented for CLI")

def refresh_modules_list():
    print("refresh_modules_list: Not implemented for CLI")
