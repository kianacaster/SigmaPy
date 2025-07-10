# arrbuf.py

# Copyright (C) 2025 John T. O'Donnell. License: GNU GPL
# Version 3. See Sigma16/README, LICENSE, and
# https://jtod.github.io/home/Sigma16

# This file is part of Sigma16. Sigma16 is free software:
# you can redistribute it and/or modify it under the terms
# of the GNU General Public License as published by the Free
# Software Foundation, Version 3 of the License. Sigma16 is
# distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
# the GNU General Public License for more details. You
# should have received a copy of the GNU General Public
# License along with Sigma16. If not, see
# <https://www.gnu.org/licenses/>.

# arrbuf.py defines the system state vector, an array
# buffer with views at word sizes 16, 32, and 64 bits.

import common
import arithmetic as arith
import architecture as arch

# -------------------------------------------------------------
# Memory map of the emulator state array
# -------------------------------------------------------------

# Sizes of state vector sections are specified in W64
# (64-bit words), ensuring that each section begins at an
# aligned location regardless of its element word size.

SCB_SIZE = 512 // 2  # emulator variables
BP_SIZE = 512 // 2  # abstract syntax tree
REG_SIZE = 32 // 2  # 16 gen, 16 sys registers
MEM_SIZE = 65536 // 4  # each location is 16 bits

MEM32_SIZE = MEM_SIZE * 4

# The array buffers are allocated with a specified size in
# bytes
STATE_VEC_SIZE_BYTES = 8 * (SCB_SIZE + BP_SIZE + REG_SIZE + MEM32_SIZE)

# Offsets of state vector sections

SCB_OFFSET64 = 0
BP_OFFSET64 = SCB_OFFSET64 + SCB_SIZE
REG_OFFSET64 = BP_OFFSET64 + BP_SIZE
MEM_OFFSET64 = REG_OFFSET64 + REG_SIZE

SCB_OFFSET32 = 2 * SCB_OFFSET64
BP_OFFSET32 = 2 * BP_OFFSET64
REG_OFFSET32 = 2 * REG_OFFSET64
MEM_OFFSET32 = 2 * MEM_OFFSET64

SCB_OFFSET16 = 2 * SCB_OFFSET32
BP_OFFSET16 = 2 * BP_OFFSET32
REG_OFFSET16 = 2 * REG_OFFSET32
MEM_OFFSET16 = 2 * MEM_OFFSET32

# -------------------------------------------------------------
# General access functions
# -------------------------------------------------------------

def read16(es, a, k):
    return arith.limit16(es.vec16[a + k])

def write16(es, a, k, x):
    es.vec16[a + k] = arith.limit16(x)

def read32(es, a, k):
    return arith.limit32(es.vec32[a + k])

def write32(es, a, k, x):
    es.vec32[a + k] = arith.limit32(x)

def read64(es, a, k):
    return es.vec64[a + k]

def write64(es, a, k, x):
    es.vec64[a + k] = x

# -------------------------------------------------------------
# System control block
# -------------------------------------------------------------

# Indices for 64-bit elements
SCB_N_INSTR_EXECUTED = 0  # count instr executed

# Indices for 32-bit elements, which follow the 64-bit
# elements
SCB_STATUS = 8  # status of system
SCB_CUR_INSTR_ADDR = 9  # addr current instr
SCB_NEXT_INSTR_ADDR = 10  # address next instr
SCB_EMWT_RUN_MODE = 11
SCB_EMWT_TRAP = 12
SCB_PAUSE_REQUEST = 13  # pause req pending
SCB_TIMER_RUNNING = 14  # timer is on
SCB_TIMER_MINOR_COUNT = 15  # count down to 0
SCB_TIMER_MAJOR_COUNT = 16  # count down to 0
SCB_TIMER_RESOLUTION = 17  # instr per tick

# SCB access functions

def write_scb(es, elt, x):
    write32(es, elt, SCB_OFFSET32, x)

def read_scb(es, elt):
    return read32(es, elt, SCB_OFFSET32)

# SCB_status codes specify the condition of the processor

SCB_RESET = 0  # after init or Reset
SCB_READY = 1  # after boot
SCB_RUNNING_GUI = 2  # running in main gui thread
SCB_RUNNING_EMWT = 3  # running in worker thread
SCB_PAUSED = 4  # after Pause command
SCB_BREAK = 5  # after Pause command
SCB_HALTED = 6  # after trap 0
SCB_BLOCKED = 7  # during blocking read
SCB_RELINQUISH = 8  # emwt relinquished control

# Clear the SCB, putting the system into initial state

def reset_scb(es):
    clear_instr_count(es)
    write_scb(es, SCB_STATUS, SCB_RESET)
    write_scb(es, SCB_N_INSTR_EXECUTED, 0)
    write_scb(es, SCB_CUR_INSTR_ADDR, 0)
    write_scb(es, SCB_NEXT_INSTR_ADDR, 0)
    write_scb(es, SCB_EMWT_RUN_MODE, 0)
    write_scb(es, SCB_EMWT_TRAP, 0)
    write_scb(es, SCB_PAUSE_REQUEST, 0)

# Convert the numeric status to a descriptive string; this
# is shown in the processor display

def show_scb_status(es):
    status = read_scb(es, SCB_STATUS)
    if status == 0:
        return "Reset"
    elif status == 1:
        return "Ready"
    elif status == 2:
        return "Running"  # run in gui
    elif status == 3:
        return "Running"  # run in emwt
    elif status == 4:
        return "Paused"
    elif status == 5:
        return "Break"
    elif status == 6:
        return "Halted"
    elif status == 7:
        return "Blocked"
    elif status == 8:
        return "Relinquish"  # relinquish
    else:
        return ""

def write_instr_count(es, n):
    write32(es, 0, SCB_OFFSET32, n)

def read_instr_count(es):
    return read32(es, 0, SCB_OFFSET32)

def clear_instr_count(es):
    write_instr_count(es, 0)

def incr_instr_count(es):
    write_instr_count(es, read_instr_count(es) + 1)

def decr_instr_count(es):
    write_instr_count(es, read_instr_count(es) - 1)

# -------------------------------------------------------------
# Registers
# -------------------------------------------------------------

def read_reg16(es, r):
    return 0 if r == 0 else read16(es, r * 2, REG_OFFSET16)

def read_reg32(es, r):
    return 0 if r == 0 else read32(es, r, REG_OFFSET32)

def write_reg16(es, r, x):
    if r != 0:
        write16(es, r * 2, REG_OFFSET16, x)

def write_reg32(es, r, x):
    if r != 0:
        write32(es, r, REG_OFFSET32, x)

# -------------------------------------------------------------
# Memory
# -------------------------------------------------------------

def read_mem16(es, a):
    return read16(es, a, MEM_OFFSET16)

def write_mem16(es, a, x):
    write16(es, a, MEM_OFFSET16, x)

def read_mem32(es, a):
    common.mode.devlog(f"read_mem32 a={a}...")
    b = a & 0xFFFFFFFE
    x = read16(es, b, MEM_OFFSET16)
    y = read16(es, b + 1, MEM_OFFSET16)
    result = (x << 16) | y
    common.mode.devlog(f"...read_mem32 b={b}" \
                       f" x = {x} ({arith.word_to_hex4(x)})" \
                       f" y = {y} ({arith.word_to_hex4(y)})" \
                       f" result = {result} ({arith.word_to_hex8(result)})")
    return result

def write_mem32(es, a, x):
    common.mode.devlog(f"write_mem32 a={a} x={arith.word_to_hex8(x)}...")
    b = a & 0xFFFFFFFE
    y = x >> 16
    z = x & 0x0000FFFF
    write16(es, b, MEM_OFFSET16, y)
    write16(es, b + 1, MEM_OFFSET16, z)
    common.mode.devlog(f"...write_mem32 b={b} x split into:" \
                       f" y = {y} ({arith.word_to_hex4(y)})" \
                       f" z = {z} ({arith.word_to_hex4(z)})")
