# assembler.py

# Copyright (C) 2025 John T. O'Donnell. License: GNU GPL Version 3
# See Sigma16/README, LICENSE, and https://github.com/jtod/Sigma16

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

# ---------------------------------------------------------------------
# assembler.py translates assembly language to machine language
# ---------------------------------------------------------------------

import re
import common
import state as st
import architecture as arch
import arithmetic as arith

# Ensure statement_spec is accessible
from architecture import statement_spec

# ---------------------------------------------------------------------
# Global
# ---------------------------------------------------------------------

# Buffers to hold generated object code

obj_buffer_limit = 8  # how many code items to allow per line
object_word_buffer = []  # list of object code words
relocation_address_buffer = []  # list of relocation addresses

# ----------------------------------------------------------------------
# GUI interface to the assembler (placeholders for now)
# ----------------------------------------------------------------------

def enter_assembler_page():
    print("enter_assembler_page: GUI function, not implemented in CLI")

def assembler_gui():
    print("assembler_gui: GUI function, not implemented in CLI")

def display_asm_source():
    print("display_asm_source: GUI function, not implemented in CLI")

def m_display_asm_source(m):
    print("m_display_asm_source: GUI function, not implemented in CLI")

def display_object_listing():
    print("display_object_listing: GUI function, not implemented in CLI")

def display_asm_listing():
    print("display_asm_listing: GUI function, not implemented in CLI")

def display_metadata():
    print("display_metadata: GUI function, not implemented in CLI")

# ----------------------------------------------------------------------
# Character set
# ----------------------------------------------------------------------

char_set = (
    "_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"  # letters
    + "0123456789"  # digits
    + " \t,;\r\n"  # separators
    + '"'  # quotes
    + "'"  # quotes
    + ".$[]()+-*"  # punctuation
    + "?`<=>!%^&{}#~@:|\\/"  # other
)

# ----------------------------------------------------------------------
# Instruction fields
# ----------------------------------------------------------------------

Field_op = "op"
Field_d = "d"
Field_a = "a"
Field_b = "b"
Field_disp = "disp"
Field_e = "e"
Field_f = "f"
Field_g = "g"
Field_h = "h"

# ----------------------------------------------------------------------
# Values
# ----------------------------------------------------------------------

def add_val(ma, s, x, y):
    result = st.Zero.copy()
    if x.origin == st.External or y.origin == st.External:
        mk_err_msg(ma, s, "Cannot perform arithmetic on external value")
    elif x.movability == st.Relocatable and y.movability == st.Relocatable:
        mk_err_msg(ma, s, "Cannot add two relocatable values")
    else:
        m = st.Relocatable if x.movability == st.Relocatable or y.movability == st.Relocatable else st.Fixed
        result = st.Value(wrap_word(x.word + y.word), st.Local, m)
    common.mode.devlog(f"add_val {x.word} + {y.word} = {result.word}")
    common.mode.devlog(f"add_val {x.to_string()} +  {y.to_string()} = {result.to_string()}")
    return result

def find_offset(here, there):
    k = abs(there.word - (here.word + 2)) if there.movability == st.Relocatable else there.word
    common.mode.devlog(f"find_offset here={here} there={there} k={k}")
    return k

def wrap_word(x):
    if x < 0:
        common.mode.devlog(f"Internal error: wrap_word {x}")
        x = 0
    return x

# ----------------------------------------------------------------------
# Evaluation of expressions
# ----------------------------------------------------------------------

def evaluate(ma, s, a, x):
    common.mode.devlog(f"Enter evaluate {type(x)} <{x}>")
    result = None
    if name_parser.search(x):
        r = ma.symbol_table.get(x)
        if r:
            result = r.value.copy()
            r.usage_lines.append(s["lineNumber"] + 1)
        else:
            mk_err_msg(ma, s, f"symbol {x} is not defined")
            result = st.mk_const_val(0)
    elif int_parser.search(x):
        result = st.mk_const_val(arith.int_to_word(int(x)))
    elif hex_parser.search(x):
        result = st.mk_const_val(arith.hex4_to_word(x[1:]))
    else:
        mk_err_msg(ma, s, f"expression {x} has invalid syntax")
        result = st.Zero.copy()
    common.mode.devlog(f"evaluate {x} returning ({result.to_string()})")
    return result

# ----------------------------------------------------------------------
# Assembly language statement
# ----------------------------------------------------------------------

def mk_asm_stmt(line_number, address, src_line):
    common.mode.devlog(f"@@@@@@@@ mk_asm_stmt {address.to_string()}")
    return {
        "lineNumber": line_number,
        "address": address,
        "srcLine": src_line,
        "listingLinePlain": "",
        "listingLineHighlightedFields": "",
        "fieldLabel": '',
        "fieldSpacesAfterLabel": '',
        "fieldOperation": '',
        "fieldSpacesAfterOperation": '',
        "fieldOperands": '',
        "fieldComment": '',
        "hasLabel": False,
        "operation": None,
        "operands": [],
        "codeSize": st.Zero,
        "orgAddr": -1,
        "reserveSize": st.Zero,
        "locCounterUpdate": st.Zero,
        "codeWord1": None,
        "codeWord2": None,
        "errors": []
    }

# ----------------------------------------------------------------------
# Error messages
# ----------------------------------------------------------------------

def mk_err_msg(ma, s, err):
    common.mode.devlog(err)
    if not s:
        s = ma.asm_stmt[len(ma.asm_stmt) - 1]
    s["errors"].append(err)
    ma.n_asm_errors += 1

def split_lines(txt):
    return txt.split("\n")

def remove_cr(xs):
    return xs.replace("\r", "")

def validate_chars(xs):
    common.mode.devlog("validate_chars")
    bad_locs = []
    for i, c in enumerate(xs):
        if c not in char_set:
            common.mode.errlog(f"validate_chars: bad char at {i} in {xs}")
            bad_locs.append(i)
            common.mode.devlog(f"i={i} charcode={ord(c)}")
    return bad_locs

# ----------------------------------------------------------------------
# Assembler
# ----------------------------------------------------------------------

def assembler(base_name, src_text):
    ai = st.AsmInfo(base_name, src_text)
    ai.metadata.push_src(
        "Line Addr Code Code Source",
        "<span class='ListingHeader'>Line Addr Code Code Source</span>",
        "<span class='ListingHeader'>Line Addr Code Code Source</span>"
    )
    asm_pass1(ai)
    asm_pass2(ai)
    if ai.n_asm_errors > 0:
        x = f"\n {ai.n_asm_errors} errors detected\n"
        y = common.highlight_field(x, 'ERR')
        ai.metadata.unshift_src(x, y, y)
    st.display_symbol_table_html(ai)
    md_text = ai.metadata.to_text()
    ai.object_text = "\n".join(ai.object_code)
    ai.md_text = md_text
    ai.obj_md = st.ObjMd(ai.asm_mod_name, ai.object_text, md_text)
    return ai

# ----------------------------------------------------------------------
# Regular expressions for the parser
# ----------------------------------------------------------------------

ident_parser = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
name_parser = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
int_parser = re.compile(r"^-?[0-9]+$")
hex_parser = re.compile(r"^\$([0-9a-fA-F]{4})$")

rc_parser = re.compile(r"^R([0-9a-fA-F]|(?:1[0-5])),([a-zA-Z][a-zA-Z0-9]*)$")

rrx_parser = re.compile(r"^R([0-9a-fA-F]|(?:1[0-5])),R([0-9a-fA-F]|(?:1[0-5])),(-?[a-zA-Z0-9_\$]+)\[R([0-9a-fA-F]|(?:1[0-5]))\]$")

rr_parser = re.compile(r"^R([0-9a-fA-F]|(?:1[0-5])),R([0-9a-fA-F]|(?:1[0-5]))]$")

# Simplified version of field: don't allow string literals
regexp_field_no_string_lit = r'((?:[^\s";]*)?)'

reg_exp_white_space = r'((?:\s+)?)'
reg_exp_comment = r'((?:.*))'

regexp_split_fields = re.compile(
    r'^'  # anchor to beginning of line
    + regexp_field_no_string_lit  # label
    + reg_exp_white_space  # separator
    + regexp_field_no_string_lit  # operation
    + reg_exp_white_space  # separator
    + regexp_field_no_string_lit  # operands
    + reg_exp_comment  # comment
)

# ----------------------------------------------------------------------
# Helper functions for parsing and code generation
# ----------------------------------------------------------------------

def require_x(ma, s, field):
    xr_parser = re.compile(r"^([^\[]+)\[(.*)\]$")
    disp = "0"
    index = 0
    xr_match = xr_parser.search(field)
    if xr_match:
        disp = xr_match.group(1)
        reg_src = xr_match.group(2)
        index = require_reg(ma, s, reg_src)
        common.mode.devlog("require_x parse failed")
    else:
        disp = field
        index = 0
    result = {"disp": disp, "index": index}
    common.mode.devlog(f"require_x field={field} disp=<{disp}> index={index}")
    return result

def require_n_operands(ma, s, n):
    k = len(s["operands"])
    if k != n:
        mk_err_msg(ma, s, f"There are {k} operands but {n} are required")
    for i in range(n):
        if i >= k or not s["operands"][i]:
            s["operands"].append("?") # Pad with '?' if not enough operands

def require_k16(ma, s, field, xs):
    common.mode.devlog(f"require_k16 <{xs}>")
    a = s["address"].word
    v = evaluate(ma, s, a, xs)
    result = v.word
    return result

def require_k4(ma, s, field, xs):
    common.mode.devlog(f"require_k4 <{xs}>")
    a = s["address"].word
    v = evaluate(ma, s, a, xs)
    result = v.word
    return result

def require_k8(ma, s, a, field, xs):
    common.mode.devlog(f"require_k8 {xs}")
    v = evaluate(ma, s, a, xs)
    result = v.word
    return result

def require_reg(ma, s, field):
    result = 0
    if (len(field) == 2 or len(field) == 3) and (field[0].lower() == "r"):
        n_text = field[1:]
        try:
            n = int(n_text, 16) if len(n_text) == 1 else int(n_text) # Handle hex for single digit, decimal for two
            if 0 <= n <= 15:
                result = n
            else:
                mk_err_msg(ma, s, f"register in {field} must be between 0 and 15")
        except ValueError:
            mk_err_msg(ma, s, f"{field} is not a valid register number")
    else:
        mk_err_msg(ma, s, f"{field} must be register, e.g. R4 or r14")
    common.mode.devlog(f"require_reg field={field} result={result}")
    return result

# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------

def parse_asm_line(ma, i):
    common.mode.devlog(f"parse_asm_line i={i}")
    s = ma.asm_stmt[i]
    line = s["srcLine"]

    # Reset fields
    s["fieldLabel"] = ''
    s["fieldOperation"] = ''
    s["fieldOperands"] = ''
    s["fieldComment"] = ''

    # 1. Separate comment
    comment_start = line.find(';')
    if comment_start != -1:
        s["fieldComment"] = line[comment_start:]
        line = line[:comment_start].strip()
    else:
        line = line.strip()

    if not line:
        s["operands"] = []
        parse_label(ma, s)
        parse_operation(ma, s)
        return

    # 2. Find label, operation, and operands
    parts = line.split(None) # Split by any whitespace, no limit

    if not parts:
        return

    # Attempt to identify label, operation, and operands
    label_candidate = parts[0]
    if label_candidate.endswith(':'):
        s["fieldLabel"] = label_candidate[:-1]
        remaining_parts = parts[1:]
    else:
        # Check if the first part is a known operation/directive
        # This is a heuristic to distinguish labels from operations when no colon is present
        # and the line starts with a potential label that is not a known operation.
        # This is tricky because a label can also be a valid operation name.
        # For now, assume if it's not a known operation, it's a label.
        # A more robust solution might involve a two-pass approach or a more complex grammar.
        if label_candidate.lower() in statement_spec or label_candidate.lower() in ["data", "module", "import", "export", "reserve", "org", "equ", "end", "block"]:
            s["fieldLabel"] = '' # No label
            remaining_parts = parts
        else:
            # Assume it's a label if it's not a known operation and no colon
            s["fieldLabel"] = label_candidate
            remaining_parts = parts[1:]

    if remaining_parts:
        s["fieldOperation"] = remaining_parts[0]
        if len(remaining_parts) > 1:
            s["fieldOperands"] = ' '.join(remaining_parts[1:])

    # Re-split operands by comma for the s["operands"] list
    s["operands"] = [op.strip() for op in s["fieldOperands"].split(',') if op.strip()]

    # 4. Finalize and parse
    s["operands"] = [op.strip() for op in s["fieldOperands"].split(',') if op.strip()]
    parse_label(ma, s)
    parse_operation(ma, s)

    common.mode.devlog(f"ParseAsmLine {s['lineNumber']}")
    common.mode.devlog(f"  fieldLabel = {s['hasLabel']} /{s['fieldLabel']}/")
    common.mode.devlog(f"  fieldOperation = /{s['fieldOperation']}/")
    common.mode.devlog(f"  operation = {show_operation(s['operation'])}")
    common.mode.devlog(f"  fieldOperands = /{s['fieldOperands']}/")
    common.mode.devlog(f"  operands = {s['operands']}")
    common.mode.devlog(f"  fieldComment = /{s['fieldComment']}/")

def parse_label(ma, s):
    if not s["fieldLabel"]:
        s["hasLabel"] = False
    elif name_parser.search(s["fieldLabel"]):
        s["hasLabel"] = True
    else:
        s["hasLabel"] = False
        mk_err_msg(ma, s, f"{s["fieldLabel"]} is not a valid label")

def parse_operation(ma, s):
    op_str = s["fieldOperation"]
    common.mode.devlog(f"parse_operation line {s["lineNumber"]} op=<{op_str}>")
    if op_str:
        # Remove leading dot if present for directives like .data
        if op_str.startswith('.'):
            op_str = op_str[1:]
        x = arch.statement_spec.get(op_str)
        if x:
            common.mode.devlog(f"parse_operation: found statement_spec {x}")
            s["operation"] = x
            if s["operation"]["ifmt"] == arch.iDir and s["operation"]["afmt"] == arch.aModule:
                ma.mod_name = s["fieldLabel"]
                ma.asm_mod_name = s["fieldLabel"]
                common.mode.devlog(f"Set module name: {ma.mod_name}")
            elif s["operation"]["ifmt"] == arch.iData and s["operation"]["afmt"] == arch.aData:
                s["codeSize"] = st.One.copy()
            elif s["operation"]["ifmt"] == arch.iDir and s["operation"]["afmt"] == arch.aReserve:
                y = evaluate(ma, s, ma.location_counter, s["fieldOperands"])
                s["reserveSize"] = y
                common.mode.devlog(f"parse Operation reserveSize={s["reserveSize"]}")
            elif s["operation"]["ifmt"] == arch.iDir and s["operation"]["afmt"] == arch.aOrg:
                y = evaluate(ma, s, ma.location_counter, s["fieldOperands"])
                s["orgAddr"] = y
                common.mode.devlog(f"parse Operation orgAddr={s["orgAddr"]}")
            else:
                s["codeSize"] = st.mk_const_val(arch.format_size(x["ifmt"]))
        else:
            s["operation"] = arch.empty_operation
            s["codeSize"] = st.Zero
            mk_err_msg(ma, s, f"{op_str} is not a valid operation")
    else:
        s["operation"] = arch.empty_operation

# ----------------------------------------------------------------------
# Assembler Pass 1
# ----------------------------------------------------------------------

def asm_pass1(ma):
    common.mode.devlog(f"Assembler Pass 1: {len(ma.asm_src_lines)} source lines")
    for i, line in enumerate(ma.asm_src_lines):
        common.mode.devlog(f"Pass 1 i={i} line=<{line}>")
        ma.asm_stmt.append(mk_asm_stmt(i, ma.location_counter.copy(), line))
        s = ma.asm_stmt[i]
        bad_char_locs = validate_chars(line)
        if bad_char_locs:
            mk_err_msg(ma, s, f"Invalid character at position {bad_char_locs}")
            mk_err_msg(ma, s, "See User Guide for list of valid characters")
            mk_err_msg(ma, s, "(Word processors often insert invalid characters)")
        parse_asm_line(ma, i)
        common.mode.devlog(f"Pass 1 {i} /{s["srcLine"]}/ address={s["address"]} codeSize={s["codeSize"]}")
        handle_label(ma, s)
        update_location_counter(ma, s, i)

def handle_label(ma, s):
    if s["hasLabel"]:
        common.mode.devlog(f"ParseAsmLine label {s["lineNumber"]} /{s["fieldLabel"]}/")
        if s["fieldLabel"] in ma.symbol_table:
            mk_err_msg(ma, s, f"{s["fieldLabel"]} has already been defined")
        elif s["fieldOperation"] == "module":
            common.mode.devlog(f"Parse line {s["lineNumber"]} label: module")
        elif s["fieldOperation"] == "equ":
            v = evaluate(ma, s, ma.location_counter, s["fieldOperands"])
            ident = st.Identifier(s["fieldLabel"], None, None, v, s["lineNumber"] + 1)
            ma.symbol_table[s["fieldLabel"]] = ident
            common.mode.devlog(f"Parse line {s["lineNumber"]} set {ident.value.to_string()}")
        elif s["fieldOperation"] == "import":
            mod = s["operands"][0]
            extname = s["operands"][1]
            v = st.ExtVal.copy()
            ident = st.Identifier(s["fieldLabel"], mod, extname, v, s["lineNumber"] + 1)
            ma.symbol_table[s["fieldLabel"]] = ident
            common.mode.devlog(f"Label import {s["lineNumber"]} locname={s["fieldLabel"]} mod={mod} extname={extname}")
        else:
            v = ma.location_counter.copy()
            common.mode.devlog(f"def label lc = {ma.location_counter.to_string()}")
            common.mode.devlog(f"def label v = {v.to_string()}")
            ident = st.Identifier(s["fieldLabel"], None, None, v, s["lineNumber"] + 1)
            common.mode.devlog(f"Parse line {s["lineNumber"]} label {s["fieldLabel"]} set {ident.value.to_string()}")
            ma.symbol_table[s["fieldLabel"]] = ident

def update_location_counter(ma, s, i):
    common.mode.devlog(f"Pass 1 {i} @ was {ma.location_counter.to_string()}")
    if s["operation"]["ifmt"] == arch.iDir and s["operation"]["afmt"] == arch.aOrg:
        v = evaluate(ma, s, ma.location_counter, s["fieldOperands"])
        ma.location_counter = v.copy()
        common.mode.devlog(f"P1 org @{ma.location_counter.to_string()}")
        common.mode.devlog(f"org {i} {ma.location_counter.to_string()}")
    elif s["operation"]["ifmt"] == arch.iDir and s["operation"]["afmt"] == arch.aReserve:
        v = evaluate(ma, s, ma.location_counter, s["fieldOperands"])
        common.mode.devlog(f"P1 reserve0 @<{ma.location_counter.to_string()}>"
)
        common.mode.devlog(f"P1 reservev v=<{v}>")
        ma.location_counter.add(v)
        s["locCounterUpdate"] = ma.location_counter.copy()
        common.mode.devlog(f"P1 reserve1 @<{ma.location_counter.to_string()}>"
)
        common.mode.devlog(f"reserve {i} {ma.location_counter.to_string()}")
    else:
        common.mode.devlog(f"Pass1 code codesize={s["codeSize"].to_string()}")
        ma.location_counter.add(s["codeSize"])
        common.mode.devlog(f"code {i} {ma.location_counter.to_string()}")

def find_ctl_idx(ma, s, xs):
    c = arch.ctl_reg.get(xs)
    i = 0
    if c:
        i = c["ctlRegIndex"]
    else:
        mk_err_msg(ma, s, f"{xs} is not a valid control register")
    common.mode.devlog(f"find_ctl_idx {xs} => {i}")
    return i

# ----------------------------------------------------------------------
# Pass 2
# ----------------------------------------------------------------------

def mk_word(op, d, a, b):
    clear = 0x000F
    return ((op & clear) << 12) | ((d & clear) << 8) | ((a & clear) << 4) | (b & clear)

def mk_word448(x, y, k8):
    clear4 = 0x000F
    clear8 = 0x00FF
    return ((x & clear4) << 12) | ((y & clear4) << 8) | (k8 & clear8)

def mk_word412(k4, k12):
    clear4 = 0x000F
    clear12 = 0x0FFF
    return ((k4 & clear4) << 12) | (k12 & clear12)

def asm_pass2(ma):
    global object_word_buffer, relocation_address_buffer
    common.mode.devlog('Assembler Pass 2')
    object_word_buffer = []
    relocation_address_buffer = []
    ma.object_code.append(f"module   {ma.asm_mod_name}")

    for i in range(len(ma.asm_stmt)):
        s = ma.asm_stmt[i]
        common.mode.devlog(f"Pass2 line {s["lineNumber"]} = /{s["srcLine"]}/")
        common.mode.devlog(f">>> pass2 operands = {s["operands"]}")
        op = s["operation"]
        common.mode.devlog(f"Pass2 op {s["fieldOperation"]} {show_operation(op)}")
        common.mode.devlog(f"Pass2 op ifmt={op["ifmt"]} afmt={op["afmt"]} pseudo={op.get("pseudo", False)}")

        if op["ifmt"] == arch.iDir and op["afmt"] == arch.aOrg:
            emit_object_words(ma)
            a = s["orgAddr"]
            a_hex = arith.word_to_hex4(a.word)
            stmt = f"org      {a_hex}"
            ma.object_code.append(stmt)
        elif op["ifmt"] == arch.iDir and op["afmt"] == arch.aReserve:
            emit_object_words(ma)
            x_hex = arith.word_to_hex4(s["locCounterUpdate"].word)
            stmt = f"org      {x_hex}"
            ma.object_code.append(stmt)
        elif op["ifmt"] == arch.iRRR and op["afmt"] == arch.aRRR:
            common.mode.devlog("pass2 iRRR/aRRR")
            require_n_operands(ma, s, 3)
            d = require_reg(ma, s, s["operands"][0])
            a = require_reg(ma, s, s["operands"][1])
            b = require_reg(ma, s, s["operands"][2])
            s["codeWord1"] = mk_word(op["opcode"][0], d, a, b)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
        elif op["ifmt"] == arch.iRRR and op["afmt"] == arch.aRR:
            common.mode.devlog("Pass2 iRRR/aRR")
            d = 0
            a = require_reg(ma, s, s["operands"][0])
            b = require_reg(ma, s, s["operands"][1])
            s["codeWord1"] = mk_word(op["opcode"][0], d, a, b)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
        elif op["ifmt"] == arch.iRX and op["afmt"] == arch.aRX:
            common.mode.devlog("***** Pass2 RX/RX")
            require_n_operands(ma, s, 2)
            d = require_reg(ma, s, s["operands"][0])
            disp_info = require_x(ma, s, s["operands"][1])
            common.mode.devlog(f"RX/RX disp = /{disp_info["disp"]}/ index={disp_info["index"]}")
            a = disp_info["index"]
            b = op["opcode"][1]
            v = evaluate(ma, s, s["address"].word + 1, disp_info["disp"])
            if v.movability == st.Relocatable:
                common.mode.devlog('RX/RX generating relocation')
                generate_relocation(ma, s, s["address"].word + 1)
            s["codeWord1"] = mk_word(op["opcode"][0], d, a, b)
            s["codeWord2"] = v.word
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
            handle_val(ma, s, s["address"].word + 1, disp_info["disp"], v, Field_disp)
        elif op["ifmt"] == arch.iRX and op["afmt"] == arch.aX:
            common.mode.devlog("***** Pass2 RX/X")
            require_n_operands(ma, s, 1)
            d = op["opcode"][2] if op.get("pseudo") else 0
            disp_info = require_x(ma, s, s["operands"][0])
            a = disp_info["index"]
            b = op["opcode"][1]
            v = evaluate(ma, s, s["address"].word + 1, disp_info["disp"])
            if v.movability == st.Relocatable:
                common.mode.devlog('RX/X generating relocation')
                generate_relocation(ma, s, s["address"].word + 1)
            s["codeWord1"] = mk_word(op["opcode"][0], d, a, b)
            s["codeWord2"] = v.word
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
            handle_val(ma, s, s["address"].word + 1, disp_info["disp"], v, Field_disp)
        elif op["ifmt"] == arch.iRX and op["afmt"] == arch.akX:
            common.mode.devlog("pass2 RX/kX")
            require_n_operands(ma, s, 2)
            k = evaluate(ma, s, s["address"].word, s["operands"][0])
            d = k.word
            disp_info = require_x(ma, s, s["operands"][1])
            a = disp_info["index"]
            b = op["opcode"][1]
            v = evaluate(ma, s, s["address"].word + 1, disp_info["disp"])
            if v.movability == st.Relocatable:
                generate_relocation(ma, s, s["address"].word + 1)
            s["codeWord1"] = mk_word(op["opcode"][0], d, a, b)
            s["codeWord2"] = v.word
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
            handle_val(ma, s, s["address"].word, s["operands"][0], k, Field_d)
            handle_val(ma, s, s["address"].word + 1, disp_info["disp"], v, Field_disp)
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.a0:
            common.mode.devlog("Pass2 iEXP1/no-operand")
            s["codeWord1"] = mk_word448(op["opcode"][0], 0, op["opcode"][1])
            s["codeWord2"] = 0
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aR:
            common.mode.devlog("pass2 EXP/R")
            require_n_operands(ma, s, 1)
            d = require_reg(ma, s, s["operands"][0])
            e = 0
            f = 0
            g = 15
            h = op["opcode"][2]
            s["codeWord1"] = mk_word448(op["opcode"][0], d, op["opcode"][1])
            s["codeWord2"] = mk_word(e, f, g, h)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aK:
            common.mode.devlog("Pass2 EXP/K")
            require_n_operands(ma, s, 1)
            dest = evaluate(ma, s, s["address"].word, s["operands"][0])
            offset = find_offset(s["address"], dest)
            common.mode.devlog(f"pc relative offset = {offset}")
            s["codeWord1"] = mk_word448(op["opcode"][0], 0, op["opcode"][1])
            s["codeWord2"] = offset
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRR:
            common.mode.devlog("pass2 EXP-RR pseudo")
            require_n_operands(ma, s, 2)
            d = require_reg(ma, s, s["operands"][0])
            e = require_reg(ma, s, s["operands"][1])
            f = 0
            g = 15
            h = op["opcode"][2] if op.get("pseudo") else 0
            s["codeWord1"] = mk_word448(op["opcode"][0], d, op["opcode"][1])
            s["codeWord2"] = mk_word(e, f, g, h)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRRR:
            common.mode.devlog('Pass2 EXP/RRR')
            require_n_operands(ma, s, 3)
            d = require_reg(ma, s, s["operands"][0])
            e = require_reg(ma, s, s["operands"][1])
            f = require_reg(ma, s, s["operands"][2])
            g = 0
            h = op["opcode"][2] if op.get("pseudo") else 0
            s["codeWord1"] = mk_word448(op["opcode"][0], d, op["opcode"][1])
            s["codeWord2"] = mk_word(e, f, g, h)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRk and not op.get("pseudo"):
            common.mode.devlog("Pass2 EXP/RK not pseudo")
            require_n_operands(ma, s, 2)
            d = require_reg(ma, s, s["operands"][0])
            efgh = s["operands"][1]
            s["codeWord1"] = mk_word448(op["opcode"][0], d, op["opcode"][1])
            s["codeWord2"] = int(efgh, 16) if efgh.startswith('$') else int(efgh) # Assuming efgh is a direct value
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRk and op.get("pseudo"):
            common.mode.devlog("Pass2 EXP/Rk")
            require_n_operands(ma, s, 2)
            ab = op["opcode"][1]
            d = require_reg(ma, s, s["operands"][0])
            e = 0
            f = require_k4(ma, s, Field_f, s["operands"][1])
            g = 0
            h = op["opcode"][2]
            s["codeWord1"] = mk_word448(op["opcode"][0], d, ab)
            s["codeWord2"] = mk_word(e, f, g, h)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRRkk and op.get("pseudo"):
            common.mode.devlog("Pass2 EXP/Rkk pseudo")
            require_n_operands(ma, s, 3)
            ab = op["opcode"][1]
            d = require_reg(ma, s, s["operands"][0])
            e = 0
            f = require_k4(ma, s, Field_e, s["operands"][1])
            g = require_k4(ma, s, Field_f, s["operands"][2])
            h = op["opcode"][2]
            s["codeWord1"] = mk_word448(op["opcode"][0], d, ab)
            s["codeWord2"] = mk_word(e, f, g, h)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRkK and not op.get("pseudo"):
            common.mode.devlog("Pass2 EXP/RkK pcr")
            require_n_operands(ma, s, 3)
            d = require_reg(ma, s, s["operands"][0])
            e = require_k4(ma, s, Field_e, s["operands"][1])
            dest = evaluate(ma, s, s["address"].word, s["operands"][2])
            offset = find_offset(s["address"], dest)
            s["codeWord1"] = mk_word448(op["opcode"][0], d, op["opcode"][1])
            s["codeWord2"] = mk_word412(e, offset)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRRk:
            common.mode.devlog("*********EXP-RRk **********")
            common.mode.devlog("pass2 aRRk")
            require_n_operands(ma, s, 3)
            ab = op["opcode"][1]
            d = require_reg(ma, s, s["operands"][0])
            e = require_reg(ma, s, s["operands"][1])
            kv = evaluate(ma, s, s["address"].word, s["operands"][2])
            f = 0
            gh = kv.word
            s["codeWord1"] = mk_word448(op["opcode"][0], d, ab)
            s["codeWord2"] = mk_word448(e, f, gh)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRRkkk:
            common.mode.devlog("pass2 aRRkkk")
            require_n_operands(ma, s, 5)
            ab = op["opcode"][1]
            d = require_reg(ma, s, s["operands"][0])
            e = require_reg(ma, s, s["operands"][1])
            f = require_k4(ma, s, Field_e, s["operands"][2])
            g = require_k4(ma, s, Field_e, s["operands"][3])
            h = require_k4(ma, s, Field_e, s["operands"][4])
            s["codeWord1"] = mk_word448(op["opcode"][0], d, ab)
            s["codeWord2"] = mk_word(e, f, g, h)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRRkk:
            common.mode.devlog("pass2 aRRkk")
            require_n_operands(ma, s, 4)
            ab = op["opcode"][1]
            d = require_reg(ma, s, s["operands"][0])
            e = require_reg(ma, s, s["operands"][1])
            f = require_k4(ma, s, Field_e, s["operands"][2])
            g = require_k4(ma, s, Field_e, s["operands"][3])
            h = op["opcode"][2]
            s["codeWord1"] = mk_word448(op["opcode"][0], d, ab)
            s["codeWord2"] = mk_word(e, f, g, h)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRC:
            common.mode.devlog("pass2 aRC")
            require_n_operands(ma, s, 2)
            rc_match = rc_parser.search(s["fieldOperands"])
            if rc_match:
                e = int(rc_match.group(1), 16) if len(rc_match.group(1)) == 1 else int(rc_match.group(1))
                ctl_reg_name = rc_match.group(2)
                ctl_reg_idx = find_ctl_idx(ma, s, ctl_reg_name)
                s["codeWord1"] = mk_word448(14, 0, op["opcode"][1])
                s["codeWord2"] = mk_word(e, ctl_reg_idx, 0, 0)
                generate_object_word(ma, s, s["address"].word, s["codeWord1"])
                generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
            else:
                mk_err_msg(ma, s, "ERROR operation requires RC operands")
        elif op["ifmt"] == arch.iEXP and op["afmt"] == arch.aRRX:
            common.mode.devlog("pass2 EXP/RRX")
            require_n_operands(ma, s, 3)
            d = require_reg(ma, s, s["operands"][0])
            e = require_reg(ma, s, s["operands"][1])
            disp_info = require_x(ma, s, s["operands"][2])
            f = disp_info["index"]
            gh = require_k8(ma, s, s["address"].word + 1, Field_gh, disp_info["disp"])
            s["codeWord1"] = mk_word448(op["opcode"][0], d, op["opcode"][1])
            s["codeWord2"] = mk_word448(e, f, gh)
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            generate_object_word(ma, s, s["address"].word + 1, s["codeWord2"])
        elif op["ifmt"] == arch.iData and op["afmt"] == arch.aData:
            common.mode.devlog(f"Pass2 {s["lineNumber"]} data")
            v = evaluate(ma, s, s["address"].word, s["fieldOperands"])
            s["codeWord1"] = v.word
            generate_object_word(ma, s, s["address"].word, s["codeWord1"])
            if v.movability == st.Relocatable:
                common.mode.devlog("relocatable data")
                generate_relocation(ma, s, s["address"].word)
        elif op["ifmt"] == arch.iDir and op["afmt"] == arch.aExport:
            common.mode.devlog('pass2 export statement')
            ident_match = ident_parser.search(s["fieldOperands"])
            if ident_match:
                ident = ident_match.group(0)
                ma.exports.append(ident)
            else:
                mk_err_msg(ma, s, "ERROR export requires identifier operand")
        else:
            common.mode.devlog('pass2 other, noOperation')

        # Reconstruct the source line for display to handle spacing correctly
        display_line_parts = []
        if s['fieldLabel']:
            display_line_parts.append(s['fieldLabel'] + ':')
        if s['fieldOperation']:
            display_line_parts.append(s['fieldOperation'])
        if s['fieldOperands']:
            display_line_parts.append(s['fieldOperands'])
        
        # Join the main parts with spaces, then add the comment
        display_line = ' '.join(display_line_parts)
        if s['fieldComment']:
            # Add a conventional separator before the comment
            display_line = f"{display_line:<40} {s['fieldComment']}"

        s["listingLinePlain"] = (
            str(s["lineNumber"] + 1).rjust(4) +
            ' ' + arith.word_to_hex4(s["address"].word) +
            ' ' + (arith.word_to_hex4(s["codeWord1"]) if s["codeWord1"] is not None else '    ') +
            ' ' + (arith.word_to_hex4(s["codeWord2"]) if s["codeWord2"] is not None else '    ') +
            ' ' + fix_html_symbols(display_line)
        )
        # For now, plain and highlighted are the same in CLI
        s["listingLineHighlightedFields"] = s["listingLinePlain"]

        ma.metadata.push_src(
            s["listingLinePlain"],
            s["listingLinePlain"],
            s["listingLineHighlightedFields"]
        )
        for error_msg in s["errors"]:
            ma.metadata.push_src(
                f'Error: {error_msg}',
                common.highlight_field(f'Error: {error_msg}','ERR'),
                common.highlight_field(f'Error: {error_msg}','ERR')
            )
    emit_object_words(ma)
    emit_relocations(ma)
    emit_exports(ma)
    emit_imports(ma)
    ma.object_code.append("")
    ma.object_text = "\n".join(ma.object_code)
    common.mode.clear_trace()

def handle_val(ma, s, a, vsrc, v, field):
    common.mode.devlog(f"handle_val {a} /{vsrc}/ {field}")
    if v.origin == st.Local and v.movability == st.Relocatable:
        generate_relocation(ma, s, a)
    elif v.origin == st.External:
        sym = ma.symbol_table.get(vsrc)
        if sym:
            mod_str = sym.mod
            extname = sym.extname
            a_str = arith.word_to_hex4(a)
            f_str = field
            x = f"import {mod_str},{extname},{a_str},{f_str}"
            ma.imports.append(x)
            common.mode.devlog(f"handle_val generate {x}")
        else:
            mk_err_msg(ma, None, f"external symbol {vsrc} undefined")
            common.mode.devlog(f"external symbol {vsrc} undefined - impossible")

def fix_html_symbols(s):
    return s.replace("<", "&lt;")

def generate_object_word(ma, s, a, x):
    object_word_buffer.append(x)
    ma.metadata.add_mapping(a, s["lineNumber"])

def emit_object_words(ma):
    global object_word_buffer
    while object_word_buffer:
        xs = object_word_buffer[:obj_buffer_limit]
        object_word_buffer = object_word_buffer[obj_buffer_limit:]
        ys = [arith.word_to_hex4(w) for w in xs]
        zs = 'data     ' + ','.join(ys)
        ma.object_code.append(zs)

def generate_relocation(ma, s, a):
    relocation_address_buffer.append(a)

def emit_relocations(ma):
    global relocation_address_buffer
    while relocation_address_buffer:
        xs = relocation_address_buffer[:obj_buffer_limit]
        relocation_address_buffer = relocation_address_buffer[obj_buffer_limit:]
        ys = [arith.word_to_hex4(w) for w in xs]
        zs = 'relocate ' + ','.join(ys)
        ma.object_code.append(zs)

def emit_imports(ma):
    common.mode.devlog("emit_imports")
    for x in ma.imports:
        ma.object_code.append(x)

def emit_exports(ma):
    common.mode.devlog(f'emit_exports{ma.exports}')
    while ma.exports:
        y = ma.exports.pop(0)
        sym = ma.symbol_table.get(y)
        if sym:
            r = "relocatable" if sym.value.movability == st.Relocatable else "fixed"
            w = arith.word_to_hex4(sym.value.word)
            common.mode.devlog(f"emit exports y={y} r={r} w={w}")
            ma.object_code.append(f"export   {y},{w},{r}")
        else:
            common.mode.devlog(f"export identifier {y} is undefined")

def show_operation(op):
    if op:
        return f"ifmt={op["ifmt"]} afmt={op["afmt"]} opcode={op["opcode"]} pseudo={op.get("pseudo", False)}"
    else:
        return "unknown op"
