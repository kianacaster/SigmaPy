# architecture.py

# Copyright (C) 2025 John T. O'Donnell. License: GNU GPL Version 3
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

# --------------------------------------------------------------------
# architecture.py defines global constants and tables specifying
# formats, opcodes, mnemonics, and flag bits
# --------------------------------------------------------------------

import common

# --------------------------------------------------------------------
# Bit indexing
# --------------------------------------------------------------------

# There are two conventions for indexing bits in a word that contains
# k bits. Then
#   - Little end (LE): the most significant (leftmost) bit has index k,
#     and the least significant (rightmost bit) has index 0.
#   - Big end (BE): the most significant (leftmost) bit has index 0,
#     and the least significant (rightmost bit) has index k.

# Functions are defined for accessing bits in a word using either
# Little End (LE) or Big End (BE) notation. For k-bit words:
#   Bit i BE = bit (k-i) LE
#   Bit i LE = bit (k-i) BE

# Earlier versions of Sigma16 (prior to 3.4) used Big End bit
# indexing. Version 3.4 switches to Little End bit indexing because
# this allows a more elegant extension to 32-bit architecture. In
# particular, a function to access bit i needs to know the wordsize k
# if Big End indexing is used, but not with Little End indexing.

# Get bit i from k-bit word w

def get_bit_in_word_le(w, i):
    return (w >> i) & 0x0001

def get_bit_in_word_be(k, w, i):
    return (w >> (k - i)) & 0x0001

# Put bit b into word x of size k in bit position i

def put_bit_in_word_le(k, x, i, b):
    return x & mask_to_clear_bit_le(i) if b == 0 else x | mask_to_set_bit_le(i)

def put_bit_in_word_be(k, x, i, b):
    return x & mask_to_clear_bit_be(k, i) if b == 0 else x | mask_to_set_bit_be(k, i)

# Generate mask to clear/set bit i in a k-bit word

def mask_to_clear_bit_le(i):
    return ~(1 << i) & 0xFFFF

def mask_to_set_bit_le(i):
    return (1 << i) & 0xFFFF

def mask_to_clear_bit_be(k, i):
    return ~(1 << (k - i)) & 0xFFFF

def mask_to_set_bit_be(k, i):
    return (1 << (k - i)) & 0xFFFF

# Access bit i in register r with k-bit words

def get_bit_in_reg_le(r, i):
    return (r.get() >> i) & 0x0001

def clear_bit_in_reg_le(r, i):
    r.put(r.get() & mask_to_clear_bit_le(i))

def set_bit_in_reg_le(r, i):
    r.put(r.get() | mask_to_set_bit_le(i))

def get_bit_in_reg_be(k, r, i):
    return (r.get() >> (k - i)) & 0x0001

def clear_bit_in_reg_be(k, r, i):
    r.put(r.get() & mask_to_clear_bit_be(k, i))

def set_bit_in_reg_be(k, r, i):
    r.put(r.get() | mask_to_set_bit_be(k, i))

# Return Boolean from bit i in word x

def extract_bool_le(x, i):
    return get_bit_in_word_le(x, i) == 1

# --------------------------------------------------------------------
# Architecture constants
# --------------------------------------------------------------------

# Should make memSize adjustable in settings, with default = 65536

mem_size = 65536  # number of memory locations = 2^16
words_per_line = 8

# Sigma16 has a standard 16-bit architecture S16, and an extended
# architecture S32 that has 32-bit registers and addresses

S16 = "S16"
S32 = "S32"

# Instruction formats

iRRR = "RRR"
iRX = "RX"
iEXP = "EXP"

# Return the size of an instruction given its format

def format_size(ifmt):
    if ifmt == iRRR:
        return 1
    elif ifmt == iRX or ifmt == iEXP:
        return 2
    else:
        return 0

# --------------------------------------------------------------------
# Assembly language statement formats
# --------------------------------------------------------------------

# Statement formats include directives as well as syntax for
# instructions. R is a general register, C is a system control
# register, X is an index-isplacement address, k is a constant. The
# statement formats allow "don't care" fields to be omitted, and
# fields to be used for either register numbers or constants.

iData = "data"
iDir = "iDir"
iEmpty = "iEmpty"

# Assembly language statement operand formats

a0 = ""  # resume
# resume timeroff
aK = "K"  # brf      loop
# ?????? brf brb ?????
aX = "X"  # jump     loop[R0]
# jump
# pseudo jumple jumpne jumpge jumpnv jumpnco
# pseudo jumplt jumpeq jumpgt jumpv jumpco
akX = "kX"  # jumpc0   3,next[R0]
# jumpc0 jumpc1
aRX = "RX"  # load     R1,xyz[R2]
# lea load store jal jumpz jumpnz testset
aR = "R"  # timeron  R1
# timeron
# pseudo invw
aRK = "RK"  # brfnz    R1,xyz
# brz brnz dispatch
aRk = "Rk"  # invb     R1,13
# pseudo invb
aRC = "RC"  # putctl   R1,status
# getctl putctl

aRkk = "Rkk"  # invb, field R1,3,12  ??
# pseudo invf
aRkK = "RkK"  # brfc0  R2,4,230
# brc0 brc1

# aRkkk    = "Rkkk"    # xorb     R1,3,8,2
# Rkkk was for andr etc but those are deprecated

# aRkkkk   = "Rkkkk"   # logicr   R1,3,8,2,xor

aRR = "RR"  # cmp      R1,R2
# cmp
# pseudo andw orw xorw
aRRk = "RRk"  #
# shiftl shiftr
aRRkk = "RRkk"  # andw pseudo
# pseudo andf orf xorf andb orb xorb
aRRkkk = "RRkkk"  # logicf   R1,R2,4,7,and
# logicf logicb extract extracti
# aRkRk    = "RkRk"    # andb     R5,4,R9,3
aRRX = "RRX"  # save     R4,R7,5[R13]
# save restore
aRkRkk = "RkRkk"  # logicc  R5,4,R9,3,and

aRRR = "RRR"  # add      R1,R2,R3
# add sub mul div addc muln divn trap
# push pop top
# pseudo andw orw xorw

aRRRkk = "RRRkk"  # inject   R1,R2,R3,5,7

# aRRkkk   = "RRk"      # extract  Rd,Rs,di,si,size
# aRkkRk   = "RkkRk"   # extract  R1,7,4,R2,12

# Assembly language directives

aData = "data"
aModule = "module"
aImport = "import"
aExport = "export"
aReserve = "reserve"
aOrg = "org"
aEqu = "equ"
aEnd = "end"
aBlock = "block"

# --------------------------------------------------------------------
# Instruction mnemonics
# --------------------------------------------------------------------

# These arrays are indexed by an opcode to give the corresponding
# mnemonic

mnemonicRRR = [
    "add", "sub", "mul", "div",  # 0-3
    "cmp", "addc", "muln", "divn",  # 4-7
    "rrr1", "rrr2", "rrr3", "rrr4",  # 8-11
    "trap", "EXP3", "EXP2", "RX"  # 12-15
]

mnemonicRX = [
    "lea", "load", "store", "jump",  # 0-3
    "jumpc0", "jumpc1", "jal", "jumpz",  # 4-7
    "jumpnz", "testset", "noprx", "noprx",  # 8-11
    "noprx", "noprx", "noprx", "noprx"  # 12-15
]

# possible future...
# "leal",     "loadl",    "storel",    "noprx"]      # c-f

mnemonicEXP = [  # ????? needs revision
    "logicf", "logicb", "nop", "shiftl",  # 00-03
    "shiftr", "extract", "nop", "push",  # 04-07
    "pop", "top", "save", "restore",  # 08-0b
    "nop", "nop", "nop", "nop",  # 0c-0f (br)
    "dispatch", "getctl", "putctl", "resume",  # 10-13
    "timeron", "timeroff"  # 14-15
]

# -------------------------------------
# Mnemonics for control registers
# -------------------------------------

# The getctl and putctl instructions contain a field indicating which
# control register to use. This record defines the names of those
# control registers (used in the assembly language) and the numeric
# index for the control register (used in the machine language).

ctl_reg = {}

ctl_reg["status"] = {"ctlRegIndex": 0}
ctl_reg["mask"] = {"ctlRegIndex": 1}
ctl_reg["req"] = {"ctlRegIndex": 2}
ctl_reg["istat"] = {"ctlRegIndex": 3}
ctl_reg["ipc"] = {"ctlRegIndex": 4}
ctl_reg["iir"] = {"ctlRegIndex": 5}
ctl_reg["iadr"] = {"ctlRegIndex": 6}
ctl_reg["vect"] = {"ctlRegIndex": 7}
ctl_reg["psegBeg"] = {"ctlRegIndex": 8}
ctl_reg["psegEnd"] = {"ctlRegIndex": 9}
ctl_reg["dsegBeg"] = {"ctlRegIndex": 10}
ctl_reg["dsegEnd"] = {"ctlRegIndex": 11}

# ----------------------------------------------------------------------
# Condition code
# ----------------------------------------------------------------------

# The condition code is a word of individual Boolean flags giving the
# results of comparisons and other conditions. R15 contains the
# condition code, except that R15 is used for an additional result
# for multiply and divide instructions.

# A word is defined for each condition code flag. An instruction may
# 'or' several of these words together to produce the final condition
# code. Bits are numbered from right to left, starting with 0. Thus
# the least significant bit has index 0, and the most significant bit
# has index 15.

# Each flag in the condition code has a symbolic name used in the
# implementation, and a display name used in the "instruction decode"
# panel on the emulator GUI. The code display
# characters are sSCVv<L=G>

# index  val  code  display   type and relation
# ----------------------------------------------
# bit 0  0001  g      >        int >
# bit 1  0002  G      G        nat >
# bit 2  0004  E      =        nat,int =
# bit 3  0008  L      L        nat <
# bit 4  0010  l      <        int <
# bit 5  0020  v      v        int overflow
# bit 6  0040  V      V        int overflow
# bit 7  0080  C      C        bin carry out, carry in (addc)
# bit 8  0100  S      S        bin carry out, carry in (addc)
# bit 9  0200  s      s        bin carry out, carry in (addc)
# bit 10 0400  f      f        logicc function result

bit_ccg = 0  # 0001 > greater than integer (two's complement)
bit_ccG = 1  # 0002 G greater than natural (binary)
bit_ccE = 2  # 0004 = equal all types
bit_ccL = 3  # 0008 L less than natural (binary)

bit_ccl = 4  # 0010 < less than integer (two's complement)
bit_ccv = 5  # 0020 v overflow integer (two's complement)
bit_ccV = 6  # 0040 V overflow natural (binary)
bit_ccC = 7  # 0080 C carry propagation natural (binary)

bit_ccS = 8  # 0100 S stack overflow
bit_ccs = 9  # 0200 s stack underflow
bit_ccf = 10  # 0400 f logicc instruction function result

# Define a mask with 1 in specified bit position
ccg = mask_to_set_bit_le(bit_ccg)
ccG = mask_to_set_bit_le(bit_ccG)
ccE = mask_to_set_bit_le(bit_ccE)
ccL = mask_to_set_bit_le(bit_ccL)
ccl = mask_to_set_bit_le(bit_ccl)
ccv = mask_to_set_bit_le(bit_ccv)
ccV = mask_to_set_bit_le(bit_ccV)
ccC = mask_to_set_bit_le(bit_ccC)
ccS = mask_to_set_bit_le(bit_ccS)
ccs = mask_to_set_bit_le(bit_ccs)
ccf = mask_to_set_bit_le(bit_ccf)

# Return a string giving symbolic representation of the condition
# code; this is used in the instruction display

def show_cc(c):
    common.mode.devlog(f"show_cc {c}")
    return (('s' if extract_bool_le(c, bit_ccs) else '') +
            ('S' if extract_bool_le(c, bit_ccS) else '') +
            ('C' if extract_bool_le(c, bit_ccC) else '') +
            ('V' if extract_bool_le(c, bit_ccV) else '') +
            ('v' if extract_bool_le(c, bit_ccv) else '') +
            ('<' if extract_bool_le(c, bit_ccl) else '') +
            ('L' if extract_bool_le(c, bit_ccL) else '') +
            ('=' if extract_bool_le(c, bit_ccE) else '') +
            ('G' if extract_bool_le(c, bit_ccG) else '') +
            ('>' if extract_bool_le(c, bit_ccg) else '') +
            ('f' if extract_bool_le(c, bit_ccf) else ''))

# ----------------------------------------------------------------------
# Status register bits
# ----------------------------------------------------------------------

# Define the bit index for each flag in the status register. "Big
# endian" notation is used, where 0 indicates the most significant
# (leftmost) bit, and index 15 indicates the least significant
# (rightmost) bit.

# When the machine boots, the registers are initialized to 0. The
# user state flag is defined so that userStateBit=0 indicates that
# the processor is in system (or supervisor) state. The reason for
# this is that the machine should boot into a state that enables the
# operating system to initialize itself, so privileged instructions
# need to be executable. Furthermore, interrupts are disabled when
# the machine boots, because interrupts are unsafe to execute until
# the interrupt vector has been initialized.

user_state_bit = 0  # 0 = system state, 1 = user state
int_enable_bit = 1  # 0 = disabled, 1 = enabled
timer_running_bit = 2  # 0 = off, 1 = running

# ----------------------------------------------------------------------
# Interrupt request and mask bits
# ----------------------------------------------------------------------

timer_bit = 0  # timer has gone off
seg_fault_bit = 1  # access invalid virtual address
stack_overflow_bit = 2  # invalid memory virtual address
stack_underflow_bit = 3  # invalid memory virtual address
user_trap_bit = 4  # user trap
overflow_bit = 5  # overflow occurred
bin_overflow_bit = 6  # overflow occurred
z_div_bit = 7  # division by 0

# ----------------------------------------------------------------------
# Assembly language statements
# ----------------------------------------------------------------------

# The instruction set is defined by a map from mnemonic to statement
# specification. The assembler uses the map to generate the machine
# language for an assembly language statement. Each entry specifies
# the instruction format, the assembly language statement format, and
# the opcode, which is represented as a list of expanding opcodes.

statement_spec = {}
empty_operation = {'ifmt': iEmpty, 'afmt': a0, 'opcode': []}

# Primary opcodes (in the op field) of 0-11 denote RRR instructions.

statement_spec["add"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [0]}
statement_spec["sub"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [1]}
statement_spec["mul"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [2]}
statement_spec["div"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [3]}
statement_spec["cmp"] = {'ifmt': iRRR, 'afmt': aRR, 'opcode': [4]}
statement_spec["addc"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [5]}
statement_spec["muln"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [6]}
statement_spec["divn"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [7]}
statement_spec["rrr1"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [8]}
statement_spec["rrr2"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [9]}
statement_spec["rrr3"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [10]}
statement_spec["rrr4"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [11]}
statement_spec["trap"] = {'ifmt': iRRR, 'afmt': aRRR, 'opcode': [12]}

# The following primary opcodes do not indicate RRR instructions:
#   13: escape to EXP3
#   14: escape to EXP
#   15: escape to RX

# RX instructions have primary opcode f and secondary opcode in b field

statement_spec["lea"] = {'ifmt': iRX, 'afmt': aRX, 'opcode': [15, 0]}
statement_spec["load"] = {'ifmt': iRX, 'afmt': aRX, 'opcode': [15, 1]}
statement_spec["store"] = {'ifmt': iRX, 'afmt': aRX, 'opcode': [15, 2]}
statement_spec["jump"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 3]}
statement_spec["jumpc0"] = {'ifmt': iRX, 'afmt': akX, 'opcode': [15, 4]}
statement_spec["jumpc1"] = {'ifmt': iRX, 'afmt': akX, 'opcode': [15, 5]}
statement_spec["jal"] = {'ifmt': iRX, 'afmt': aRX, 'opcode': [15, 6]}
statement_spec["jumpz"] = {'ifmt': iRX, 'afmt': aRX, 'opcode': [15, 7]}
statement_spec["jumpnz"] = {'ifmt': iRX, 'afmt': aRX, 'opcode': [15, 8]}
statement_spec["testset"] = {'ifmt': iRX, 'afmt': aRX, 'opcode': [15, 9]}

# EXP instructions are represented in 2 words, with primary opcode e
# and an 8-bit secondary opcode in the ab field, where ab >= 8. (If
# 0 <= ab <8 then the instruction is EXP1 format.)

statement_spec["logicf"] = {'ifmt': iEXP, 'afmt': aRRkkk, 'opcode': [14, 0]}
statement_spec["logicb"] = {'ifmt': iEXP, 'afmt': aRRkkk, 'opcode': [14, 1]}
statement_spec["shiftl"] = {'ifmt': iEXP, 'afmt': aRRk, 'opcode': [14, 3]}
statement_spec["shiftr"] = {'ifmt': iEXP, 'afmt': aRRk, 'opcode': [14, 4]}
statement_spec["extract"] = {'ifmt': iEXP, 'afmt': aRRkkk, 'opcode': [14, 5]}
statement_spec["extracti"] = {'ifmt': iEXP, 'afmt': aRRkkk, 'opcode': [14, 6]}
statement_spec["push"] = {'ifmt': iEXP, 'afmt': aRRR, 'opcode': [14, 7]}
statement_spec["pop"] = {'ifmt': iEXP, 'afmt': aRRR, 'opcode': [14, 8]}
statement_spec["top"] = {'ifmt': iEXP, 'afmt': aRRR, 'opcode': [14, 9]}
statement_spec["save"] = {'ifmt': iEXP, 'afmt': aRRX, 'opcode': [14, 10]}
statement_spec["restore"] = {'ifmt': iEXP, 'afmt': aRRX, 'opcode': [14, 11]}
statement_spec["brc0"] = {'ifmt': iEXP, 'afmt': aRkK, 'opcode': [14, 12]}
statement_spec["brc1"] = {'ifmt': iEXP, 'afmt': aRkK, 'opcode': [14, 13]}
statement_spec["brz"] = {'ifmt': iEXP, 'afmt': aRK, 'opcode': [14, 14]}
statement_spec["brnz"] = {'ifmt': iEXP, 'afmt': aRK, 'opcode': [14, 15]}
statement_spec["dispatch"] = {'ifmt': iEXP, 'afmt': aRk, 'opcode': [14, 16], 'pseudo': False}
statement_spec["getctl"] = {'ifmt': iEXP, 'afmt': aRC, 'opcode': [14, 17]}
statement_spec["putctl"] = {'ifmt': iEXP, 'afmt': aRC, 'opcode': [14, 18]}
statement_spec["resume"] = {'ifmt': iEXP, 'afmt': a0, 'opcode': [14, 19]}
statement_spec["timeron"] = {'ifmt': iEXP, 'afmt': aR, 'opcode': [14, 20, 0]}
statement_spec["timeroff"] = {'ifmt': iEXP, 'afmt': a0, 'opcode': [14, 21]}

# Assembler directives

statement_spec["data"] = {'ifmt': iData, 'afmt': aData, 'opcode': []}
statement_spec["module"] = {'ifmt': iDir, 'afmt': aModule, 'opcode': []}
statement_spec["import"] = {'ifmt': iDir, 'afmt': aImport, 'opcode': []}
statement_spec["export"] = {'ifmt': iDir, 'afmt': aExport, 'opcode': []}
statement_spec["reserve"] = {'ifmt': iDir, 'afmt': aReserve, 'opcode': []}
statement_spec["org"] = {'ifmt': iDir, 'afmt': aOrg, 'opcode': []}
statement_spec["equ"] = { "ifmt": iDir, "afmt": aEqu,      "opcode": [0,0,0,0], "pseudo": True }
statement_spec["end"] = { "ifmt": iDir, "afmt": aEnd,      "opcode": [0,0,0,0], "pseudo": True }
statement_spec["block"] = { "ifmt": iDir, "afmt": aBlock,    "opcode": [0,0,0,0], "pseudo": True }

# -------------------------------------
# Pseudoinstructions
# -------------------------------------

# JX is a pseudoinstruction format: an assembly language statement
# format which omits the d field, but the machine language format is
# RX, where R0 is used for the d field. For example, jump loop[R5]
# doesn't require d field in assembly language, but the machine
# language uses d=R0.

# Pseudoinstructions that generate jumpc0 (secondary opcode = 4)

statement_spec["jumple"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 4, bit_ccg], 'pseudo': True}
statement_spec["jumpne"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 4, bit_ccE], 'pseudo': True}
statement_spec["jumpge"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 4, bit_ccl], 'pseudo': True}
statement_spec["jumpnv"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 4, bit_ccv], 'pseudo': True}
statement_spec["jumpnco"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 4, bit_ccC], 'pseudo': True}

# Pseudoinstructions that generate jumpc1 (secondary opcode = 5)

statement_spec["jumplt"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 5, bit_ccl], 'pseudo': True}
statement_spec["jumpeq"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 5, bit_ccE], 'pseudo': True}
statement_spec["jumpgt"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 5, bit_ccg], 'pseudo': True}
statement_spec["jumpv"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 5, bit_ccv], 'pseudo': True}
statement_spec["jumpco"] = {'ifmt': iRX, 'afmt': aX, 'opcode': [15, 5, bit_ccC], 'pseudo': True}

# Mnemonics for logic pseudo instructions

statement_spec["invw"] = {'ifmt': iEXP, 'afmt': aR, 'opcode': [14, 0, 12], 'pseudo': True}
statement_spec["andw"] = {'ifmt': iEXP, 'afmt': aRR, 'opcode': [14, 0, 1], 'pseudo': True}
statement_spec["orw"] = {'ifmt': iEXP, 'afmt': aRR, 'opcode': [14, 0, 7], 'pseudo': True}
statement_spec["xorw"] = {'ifmt': iEXP, 'afmt': aRR, 'opcode': [14, 0, 6], 'pseudo': True}
statement_spec["invf"] = {'ifmt': iEXP, 'afmt': aRkk, 'opcode': [14, 0, 12], 'pseudo': True}
statement_spec["andf"] = {'ifmt': iEXP, 'afmt': aRRkk, 'opcode': [14, 0, 1], 'pseudo': True}
statement_spec["orf"] = {'ifmt': iEXP, 'afmt': aRRkk, 'opcode': [14, 0, 7], 'pseudo': True}
statement_spec["xorf"] = {'ifmt': iEXP, 'afmt': aRRkk, 'opcode': [14, 0, 6], 'pseudo': True}

# Mnemonics for logicb pseudo instructions

statement_spec["invb"] = {'ifmt': iEXP, 'afmt': aRk, 'opcode': [14, 1, 12], 'pseudo': True}
statement_spec["setb"] = {'ifmt': iEXP, 'afmt': aRk, 'opcode': [14, 1, 15], 'pseudo': True}
statement_spec["clearb"] = {'ifmt': iEXP, 'afmt': aRk, 'opcode': [14, 1, 0], 'pseudo': True}

statement_spec["andb"] = {'ifmt': iEXP, 'afmt': aRRkk, 'opcode': [14, 1, 1], 'pseudo': True}
statement_spec["orb"] = {'ifmt': iEXP, 'afmt': aRRkk, 'opcode': [14, 1, 7], 'pseudo': True}
statement_spec["xorb"] = {'ifmt': iEXP, 'afmt': aRRkk, 'opcode': [14, 1, 6], 'pseudo': True}
statement_spec["copyb"] = {'ifmt': iEXP, 'afmt': aRRkk, 'opcode': [14, 1, 5], 'pseudo': True}
statement_spec["copybi"] = {'ifmt': iEXP, 'afmt': aRRkk, 'opcode': [14, 1, 10], 'pseudo': True}

# Mnemonic for bit field

statement_spec["field"] = {'ifmt': iEXP, 'afmt': aRkk, 'opcode': [14, 5], 'pseudo': True}

clear_int_enable = mask_to_clear_bit_be(16, int_enable_bit)
set_system_state = mask_to_clear_bit_be(16, user_state_bit)