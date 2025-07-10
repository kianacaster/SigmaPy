# emulator.py

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
# emulator.py defines the machine language semantics
# -------------------------------------------------------------------------

import common
import architecture as arch
import arithmetic as arith

import state as st
import assembler as asm
import linker as link
import s16module as smod

# -----------------------------------------------------------------------
# Default parameters
# -----------------------------------------------------------------------

default_timer_resolution = 0

# -----------------------------------------------------------------------
# Access to system control register flags
# -----------------------------------------------------------------------

def get_status_bit(es, i):
    r = es.status_reg.get()
    x = arch.get_bit_in_word_le(r, i)
    return x

def set_status_bit(es, i, x):
    r = es.status_reg.get()
    y = arch.put_bit_in_word_le(16, r, i, x)
    es.status_reg.put(y)

# -----------------------------------------------------------------------
# Interface to emulator
# -----------------------------------------------------------------------

def limit_address(es, x):
    return x & es.address_mask

def show_es_info(es):
    return (f"show_es_info thread={es.thread_host}\n" +
            f"  reg_fetched = {es.copyable["regFetched"]}\n" +
            f"  reg_stored = {es.copyable["regStored"]}\n" +
            f"  mem_fetch_instr_log = {es.copyable["memFetchInstrLog"]}\n" +
            f"  mem_fetch_data_log = {es.copyable["memFetchDataLog"]}\n" +
            f"  mem_store_log = {es.copyable["memStoreLog"]}\n")

mode_highlight_access = True

def init_reg_highlighting(es):
    es.reg_fetched_old = []
    es.reg_stored_old = []
    es.copyable["regFetched"] = []
    es.copyable["regStored"] = []

# ------------------------------------------------------------------------
# Emulator state
# ------------------------------------------------------------------------

init_es_copyable = {
    "breakPCvalue": 0,
    "breakEnabled": False,
    "regFetched": [],
    "regStored": [],
    "memFetchInstrLog": [],
    "memFetchDataLog": [],
    "memStoreLog": [],
    "memFetchInstrLogOld": [],
    "memFetchDataLogOld": [],
    "memStoreLogOld": []
}

def show_copyable(x):
    print("show_copyable")
    print(f"breakEnabled = {x["breakEnabled"]}")
    print(f"breakPCvalue = {x["breakPCvalue"]}")
    print(f"regFetched = {x["regFetched"]}")
    print(f"regStored = {x["regStored"]}")
    print(f"memFetchInstrLog = {x["memFetchInstrLog"]}")
    print(f"memFetchDataLog = {x["memFetchDataLog"]}")
    print(f"memStoreLog = {x["memStoreLog"]}")

class EmulatorState:
    def __init__(self, thread_host, arrbuf_module, f=None, g=None, h=None):
        print(f"new EmulatorState host={thread_host}")
        self.thread_host = thread_host
        self.ab = arrbuf_module # Store the arrbuf module in the emulator state
        self.copyable = init_es_copyable

        self.arch = arch.S16

        self.clear_processor_display = None
        self.init_run_display = f
        self.during_run_display = g
        self.end_run_display = h
        self.wasm_memory = None
        self.shm = None
        self.vecbuf = None
        self.vec16 = [0] * (self.ab.STATE_VEC_SIZE_BYTES // 2) # Initialize with zeros
        self.vec32 = [0] * (self.ab.STATE_VEC_SIZE_BYTES // 4)
        self.vec64 = [0] * (self.ab.STATE_VEC_SIZE_BYTES // 8)
        self.em_run_capability = common.ES_gui_thread
        self.em_run_thread = common.ES_gui_thread
        self.start_time = None
        self.event_timer = None
        self.em_instr_slice_size = 500
        self.slice_unlimited = True
        self.instr_looper_delay = 1000
        self.instr_looper_show = False
        self.break_enabled = False
        self.do_interrupt = 0
        self.io_log_buffer = ""
        self.address_mask = arith.word16mask
        self.pc = None
        self.ir = None
        self.adr = None
        self.dat = None
        self.status_reg = None
        self.mask = None
        self.req = None
        self.rstat = None
        self.rpc = None
        self.vect = None
        self.bpseg = None
        self.epseg = None
        self.bdseg = None
        self.edseg = None
        self.regfile = []
        self.control_registers = []
        self.n_registers = 0
        self.register = []
        self.ir_op = 0
        self.ir_d = 0
        self.ir_a = 0
        self.ir_b = 0
        self.ea = 0
        self.instr_disp = 0
        self.field_e = 0
        self.field_f = 0
        self.field_g = 0
        self.field_h = 0
        self.field_gh = 0
        self.instr_op_code = None
        self.instr_code_str = ""
        self.instr_fmt_str = ""
        self.instr_code = 0
        self.instr_op = ""
        self.instr_args = ""
        self.instr_ea = None
        self.instr_ea_str = ""
        self.instr_effect = []
        self.cur_instr_addr = 0
        self.next_instr_addr = 0
        self.instr_code_elt = None
        self.instr_fmt_elt = None
        self.instr_op_elt = None
        self.instr_args_elt = None
        self.instr_ea_elt = None
        self.instr_cc_elt = None
        self.instr_effect1_elt = None
        self.instr_effect2_elt = None
        self.copyable = init_es_copyable

        common.mode.devlog(f"em.initialize_machine_state thread={self.thread_host}")

        for i in range(16):
            reg_name = f'R{i}'
            self.regfile.append(GenRegister(self, reg_name, reg_name, arith.word_to_hex4, self.ab))

        self.pc = GenRegister(self, 'pc', 'pcElt', arith.word_to_hex4, self.ab)
        self.ir = GenRegister(self, 'ir', 'irElt', arith.word_to_hex4, self.ab)
        self.adr = GenRegister(self, 'adr', 'adrElt', arith.word_to_hex4, self.ab)
        self.dat = GenRegister(self, 'dat', 'datElt', arith.word_to_hex4, self.ab)

        self.status_reg = GenRegister(self, 'statusreg', 'statusElt', arith.word_to_hex4, self.ab)
        self.mask = GenRegister(self, 'mask', 'maskElt', arith.word_to_hex4, self.ab)
        self.req = GenRegister(self, 'req', 'reqElt', arith.word_to_hex4, self.ab)
        self.rstat = GenRegister(self, 'rstat', 'rstatElt', arith.word_to_hex4, self.ab)
        self.rpc = GenRegister(self, 'rpc', 'rpcElt', arith.word_to_hex4, self.ab)
        self.iir = GenRegister(self, 'iir', 'iirElt', arith.word_to_hex4, self.ab)
        self.iadr = GenRegister(self, 'iadr', 'iadrElt', arith.word_to_hex4, self.ab)
        self.vect = GenRegister(self, 'vect', 'vectElt', arith.word_to_hex4, self.ab)

        self.bpseg = GenRegister(self, 'bpseg', 'bpsegElt', arith.word_to_hex4, self.ab)
        self.epseg = GenRegister(self, 'epseg', 'epsegElt', arith.word_to_hex4, self.ab)
        self.bdseg = GenRegister(self, 'bdseg', 'bdsegElt', arith.word_to_hex4, self.ab)
        self.edseg = GenRegister(self, 'edseg', 'edsegElt', arith.word_to_hex4, self.ab)

        self.control_registers = [
            self.pc, self.ir, self.adr, self.dat,
            self.status_reg, self.mask, self.req, self.rstat, self.rpc,
            self.iir, self.iadr,
            self.vect,
            self.bpseg, self.epseg, self.bdseg, self.edseg
        ]

        mem_initialize(self)
        reset_registers(self)

ctl_reg_index_offset = 20
sys_ctl_reg_idx = 0
register_index = 0

class GenRegister:
    def __init__(self, es, reg_name, elt_name, show_fcn, arrbuf_module):
        self.ab = arrbuf_module
        self.es = es
        self.reg_st_index = es.n_registers
        self.reg_number = es.n_registers
        es.n_registers += 1
        self.reg_name = reg_name
        self.elt_name = elt_name
        self.show = show_fcn
        self.elt = None # GUI element, will be set later
        es.register.append(self)

    def get(self):
        x = self.ab.read_reg16(self.es, self.reg_st_index)
        self.es.copyable["regFetched"].append((self.reg_number, x))
        return x

    def get32(self):
        self.es.copyable["regFetched"].append(self.reg_number)
        x = self.ab.read_reg32(self.es, self.reg_st_index)
        return x

    def put(self, x):
        self.es.copyable["regStored"].append((self.reg_number, x))
        self.ab.write_reg16(self.es, self.reg_number, x)
        # if self.reg_idx < 16: # register file
        #     self.es.instr_effect.append(["R", self.reg_number, x, self.reg_name])

    def put32(self, x):
        self.es.copyable["regStored"].append(self.reg_number)
        self.ab.write_reg32(self.es, self.reg_number, x)
        # if self.reg_idx < 16: # register file
        #     self.es.instr_effect.append(["R", self.reg_number, x, self.reg_name])

    def highlight(self, key):
        # GUI-specific, placeholder
        pass

    def refresh(self):
        # GUI-specific, placeholder
        pass

def reset_registers(es):
    common.mode.devlog(f"Resetting registers {es.thread_host} {es.n_registers}")
    for i in range(es.n_registers):
        es.register[i].put(0)

def mem_clear(es):
    for a in range(arch.mem_size):
        es.ab.write_mem16(es, a, 0)

def mem_fetch_instr(es, a):
    x = es.ab.read_mem16(es, a)
    es.copyable["memFetchInstrLog"].append((a, x))
    common.mode.devlog(f"mem_fetch_instr a={arith.word_to_hex4(a)} x={arith.word_to_hex4(x)}")
    return x

def mem_fetch_data(es, a):
    x = es.ab.read_mem16(es, a)
    es.copyable["memFetchDataLog"].append((a, x))
    return x

def mem_store(es, a, x):
    es.copyable["memStoreLog"].append((a, x))
    es.instr_effect.append(["M", a, x])
    es.ab.write_mem16(es, a, x)

# -------------------------------------------------------------------------
# Initialize machine state
# -------------------------------------------------------------------------

def proc_reset(es):
    common.mode.devlog("reset the processor")
    es.ab.reset_scb(es)
    reset_registers(es)
    mem_clear(es)
    timer_initialize(es, default_timer_resolution)

def mem_initialize(es):
    if es.thread_host == common.ES_gui_thread:
        mem_clear(es)

# -------------------------------------------------------------------------
# Decode instruction
# -------------------------------------------------------------------------

def show_instr_decode(es):
    es.instr_code_str = (arith.word_to_hex4(es.instr_code) if es.instr_code else "") + \
                        (" " + arith.word_to_hex4(es.instr_disp) if es.instr_disp else "")
    es.instr_ea_str = arith.word_to_hex4(es.instr_ea) if es.instr_ea else ""
    common.mode.devlog(f"show_instr_decode fmt = {es.instr_fmt_str}")

# -------------------------------------------------------------------------
# Controlling instruction execution
# -------------------------------------------------------------------------

def main_run(es):
    es.slice_unlimited = False
    instruction_looper(es)

def instruction_looper(es):
    icount = 0
    continue_running = True
    finished = False
    external_break = False

    while continue_running:
        execute_instruction(es)
        icount += 1
        status = es.ab.read_scb(es, es.ab.SCB_STATUS)
        common.mode.devlog(f"looper after instruction, status={status}")

        if status in [es.ab.SCB_HALTED, es.ab.SCB_PAUSED, es.ab.SCB_BREAK, es.ab.SCB_RELINQUISH]:
            finished = True

        external_break = es.copyable["breakEnabled"] and (es.pc.get() == es.copyable["breakPCvalue"])
        if external_break:
            finished = True

        pause_req = es.ab.read_scb(es, es.ab.SCB_PAUSE_REQUEST) != 0
        count_ok = es.slice_unlimited or icount < es.em_instr_slice_size
        continue_running = not finished and not pause_req and count_ok

    common.mode.devlog('discontinue instruction looper')
    if pause_req and status != es.ab.SCB_HALTED:
        common.mode.devlog("pausing execution")
        es.ab.write_scb(es, es.ab.SCB_STATUS, es.ab.SCB_PAUSED)
        es.ab.write_scb(es, es.ab.SCB_PAUSE_REQUEST, 0)
    elif external_break:
        print("Stopping at breakpoint")
        es.ab.write_scb(es, es.ab.SCB_STATUS, es.ab.SCB_BREAK)

    if finished:
        if es.end_run_display:
            es.end_run_display(es)
    else:
        if es.during_run_display:
            es.during_run_display(es)
        # In a real GUI, this would be a QTimer.singleShot or similar
        # For CLI, we just continue immediately or use a small delay if needed
        instruction_looper(es) # Recursive call for simplicity in CLI

# -------------------------------------------------------------------------
# Accessing the timer
# -------------------------------------------------------------------------

def timer_initialize(es, resolution):
    es.ab.write_scb(es, es.ab.SCB_TIMER_RUNNING, 0)
    es.ab.write_scb(es, es.ab.SCB_TIMER_MINOR_COUNT, 0)
    es.ab.write_scb(es, es.ab.SCB_TIMER_MAJOR_COUNT, 0)
    es.ab.write_scb(es, es.ab.SCB_TIMER_RESOLUTION, resolution)

def timer_display(es):
    r = es.ab.read_scb(es, es.ab.SCB_TIMER_RUNNING)
    if r:
        x = es.ab.read_scb(es, es.ab.SCB_TIMER_MINOR_COUNT)
        y = es.ab.read_scb(es, es.ab.SCB_TIMER_MAJOR_COUNT)
        print(f"Timer: running={r} minor={x} major={y}")

def timer_is_running(es):
    return es.ab.read_scb(es, es.ab.SCB_TIMER_RUNNING)

def timer_start(es, x):
    print(f"Starting timer ({x})")
    es.ab.write_scb(es, es.ab.SCB_TIMER_RUNNING, 1)
    es.ab.write_scb(es, es.ab.SCB_TIMER_MAJOR_COUNT, x)
    es.ab.write_scb(es, es.ab.SCB_TIMER_MINOR_COUNT, 0)
    set_status_bit(es, arch.timer_running_bit, 1)

def timer_stop(es):
    print("Stopping timer")
    es.ab.write_scb(es, es.ab.SCB_TIMER_RUNNING, 0)
    es.ab.write_scb(es, es.ab.SCB_TIMER_MAJOR_COUNT, 0)
    es.ab.write_scb(es, es.ab.SCB_TIMER_MINOR_COUNT, 0)
    set_status_bit(es, arch.timer_running_bit, 0)

def timer_tick(es):
    timer_display(es)
    timer_running = es.ab.read_scb(es, es.ab.SCB_TIMER_RUNNING)
    if timer_running:
        timer_display(es)
        x = es.ab.read_scb(es, es.ab.SCB_TIMER_MINOR_COUNT)
        if x > 0:
            es.ab.write_scb(es, es.ab.SCB_TIMER_MINOR_COUNT, x - 1)
            print(f"timer_tick minor count = {x}")
        else:
            y = es.ab.read_scb(es, es.ab.SCB_TIMER_MAJOR_COUNT)
            if y > 0:
                es.ab.write_scb(es, es.ab.SCB_TIMER_MAJOR_COUNT, y - 1)
                a = es.ab.read_scb(es, es.ab.SCB_TIMER_RESOLUTION)
                es.ab.write_scb(es, es.ab.SCB_TIMER_MINOR_COUNT, a)
            else:
                es.ab.write_scb(es, es.ab.SCB_TIMER_RUNNING, 0)
                req_old = es.req.get()
                req_new = arith.set_bit(req_old, arch.timer_bit, 1)
                es.req.put(req_new)
                print('Timer interrupt request')

# -------------------------------------------------------------------------
# Wrapper around instruction execution
# -------------------------------------------------------------------------

def clear_mem_logging(es):
    es.copyable["memFetchInstrLog"] = []
    es.copyable["memFetchInstrLogOld"] = []
    es.copyable["memFetchDataLog"] = []
    es.copyable["memFetchDataLogOld"] = []
    es.copyable["memStoreLog"] = []
    es.copyable["memStoreLogOld"] = []

def clear_reg_logging(es):
    es.copyable["regFetched"] = []
    es.copyable["regStored"] = []

# -------------------------------------------------------------------------
# Machine language semantics
# -------------------------------------------------------------------------

def clear_instr_decode(es):
    es.instr_op_code = None
    es.instr_disp = None
    es.instr_code_str = ""
    es.instr_fmt_str = ""
    es.instr_op = ""
    es.instr_args = ""
    es.instr_ea = None
    es.instr_ea_str = ""
    es.instr_effect1 = ""
    es.instr_effect2 = ""
    es.instr_effect = []

def execute_instruction(es):
    common.mode.devlog(f"em.execute_instruction starting")
    clear_reg_logging(es)
    clear_mem_logging(es)
    clear_instr_decode(es)

    # Store PC before execution, this is the address of the instruction being executed
    executed_instr_addr = es.pc.get() 

    es.ab.write_scb(es, es.ab.SCB_CUR_INSTR_ADDR, executed_instr_addr)

    mr = es.mask.get() & es.req.get()
    common.mode.devlog(f"interrupt mr = {arith.word_to_hex4(mr)}")
    if arch.get_bit_in_reg_le(es.status_reg, arch.int_enable_bit) and mr:
        common.mode.devlog("execute instruction: interrupt")
        print('Interrupting')
        i = 0
        while i < 16 and arch.get_bit_in_word_le(mr, i) == 0:
            i += 1
        common.mode.devlog(f"\n*** Interrupt {i} ***")
        es.rpc.put(es.pc.get())
        es.rstat.put(es.status_reg.get())
        es.iir.put(es.ir.get())
        es.iadr.put(es.adr.get())
        arch.clear_bit_in_reg_le(es.req, i)
        es.pc.put(limit_address(es, es.vect.get() + 2 * i))
        es.status_reg.put(es.status_reg.get() & \
                           arch.mask_to_clear_bit_le(arch.int_enable_bit) & \
                           arch.mask_to_clear_bit_le(arch.user_state_bit))
        timer_stop(es)
        return

    common.mode.devlog("no interrupt, proceeding...")
    es.instr_code = mem_fetch_instr(es, executed_instr_addr)
    common.mode.devlog(f"ExInstr ir={arith.word_to_hex4(es.instr_code)}")
    es.ir.put(es.instr_code)
    es.next_instr_addr = arith.incr_address(es, executed_instr_addr, 1)
    es.pc.put(limit_address(es, es.next_instr_addr))
    es.ab.write_scb(es, es.ab.SCB_NEXT_INSTR_ADDR, es.next_instr_addr)
    common.mode.devlog(f"ExInstr pcnew={arith.word_to_hex4(es.next_instr_addr)}")

    temp_instr = es.ir.get()
    common.mode.devlog(f"ExInstr instr={arith.word_to_hex4(temp_instr)}")
    es.ir_b = temp_instr & 0x000F
    temp_instr >>= 4
    es.ir_a = temp_instr & 0x000F
    temp_instr >>= 4
    es.ir_d = temp_instr & 0x000F
    temp_instr >>= 4
    es.ir_op = temp_instr & 0x000F

    es.instr_fmt_str = "RRR"
    es.instr_op_str = arch.mnemonicRRR[es.ir_op]
    common.mode.devlog(f"ExInstr dispatch primary opcode {es.ir_op}")

    dispatch_primary_opcode[es.ir_op](es)
    es.ab.incr_instr_count(es)
    timer_tick(es)

    # After instruction execution and PC update, set cur_instr_addr to the instruction that was just executed
    es.cur_instr_addr = executed_instr_addr

    



# -------------------------------------------------------------------------
# Instruction pattern functions
# -------------------------------------------------------------------------

def nop(es):
    pass

def ab_dac(f):
    def inner(es):
        a = es.regfile[es.ir_a].get()
        b = es.regfile[es.ir_b].get()
        primary, secondary = f(a, b)
        es.regfile[es.ir_a].put(primary)
        if es.ir_a < 15:
            es.regfile[15].put(secondary)
    return inner

def rrrc(f):
    def inner(es):
        a = es.regfile[es.ir_a].get()
        b = es.regfile[es.ir_b].get()
        primary, secondary = f(a, b)
        es.regfile[es.ir_d].put(primary)
        if es.ir_d < 15:
            es.regfile[15].put(secondary)
    return inner

def rd(f):
    def inner(es):
        a = es.regfile[es.ir_a].get()
        primary = f(a)
        es.regfile[es.ir_d].put(primary)
    return inner

def rrd(f):
    def inner(es):
        a = es.regfile[es.ir_a].get()
        b = es.regfile[es.ir_b].get()
        primary = f(a, b)
        es.regfile[es.ir_d].put(primary)
    return inner

def ab_c(f):
    def inner(es):
        a = es.regfile[es.ir_a].get()
        b = es.regfile[es.ir_b].get()
        cc = f(a, b)
        common.mode.devlog(f"ab_c cc={cc}")
        es.regfile[15].put(cc)
    return inner

def dab(f):
    def inner(es):
        f(es)
    return inner

def cab_dc(f):
    def inner(es):
        c = es.regfile[15].get()
        a = es.regfile[es.ir_a].get()
        b = es.regfile[es.ir_b].get()
        primary, secondary = f(c, a, b)
        es.regfile[es.ir_d].put(primary)
        if es.ir_d < 15:
            es.regfile[15].put(secondary)
    return inner

def cab_c(f):
    def inner(es):
        c = es.regfile[15].get()
        a = es.regfile[es.ir_a].get()
        b = es.regfile[es.ir_b].get()
        secondary = f(c, a, b)
        es.regfile[15].put(secondary)
    return inner

def cab_dca(f):
    def inner(es):
        c = es.regfile[15].get()
        a = es.regfile[es.ir_a].get()
        b = es.regfile[es.ir_b].get()
        primary, secondary, tertiary = f(c, a, b)
        es.regfile[es.ir_d].put(primary)
        if es.ir_d < 15:
            es.regfile[15].put(secondary)
        es.regfile[es.ir_a].put(tertiary)
    return inner

def exp2_add32(es):
    print("exp2_add32 start")
    x = es.regfile[es.field_e].get32()
    print(f"exp2_add32 x = {x}")
    y = es.regfile[es.field_f].get32()
    print(f"exp2_add32 y = {y}")
    result = x + y
    print(f"exp2_add32 result = {result}")
    es.regfile[es.ir_d].put32(result)
    print("exp2_add32 end")

def op_trap(es):
    print("op_trap")
    if es.thread_host == common.ES_gui_thread:
        common.mode.devlog("handle trap in main thread")
        code = es.regfile[es.ir_d].get()
        print(f"trap code={code}")
        if code >= 255:
            handle_user_trap(es, code)
        elif code == 0:
            print("Trap: halt")
            common.mode.devlog("Trap: halt")
            es.ab.write_scb(es, es.ab.SCB_STATUS, es.ab.SCB_HALTED)
        elif code == 1:
            print('trap: nonblocking read')
            trap_read(es)
        elif code == 2:
            print('trap: nonblocking write')
            trap_write(es)
        elif code == 3:
            print('trap: blocking read (not implemented)')
        elif code == 4:
            print('trap: break')
            es.ab.write_scb(es, es.ab.SCB_STATUS, es.ab.SCB_BREAK)
        else:
            common.mode.devlog(f"trap with unbound code = {code}")
    elif es.thread_host == common.ES_worker_thread:
        print("**** handle trap in worker thread")
        print("emworker: relinquish control on a trap")
        es.ab.write_scb(es, es.ab.SCB_STATUS, es.ab.SCB_RELINQUISH)
        print(f"trap relinquish before fixup, pc = {es.pc.get()}")
        es.pc.put(limit_address(es, es.ab.read_scb(es, es.ab.SCB_CUR_INSTR_ADDR)))
        print(f"trap relinquish after fixup, pc = {es.pc.get()}")
    else:
        print(f"system error: trap has bad shm_token")

def handle_user_trap(es, code):
    print("handle_user_trap")
    aval = es.regfile[es.ir_a].get()
    bval = es.regfile[es.ir_b].get()
    print(f"d={es.ir_d} code={arith.word_to_hex4(code)}")
    print(f"a={es.ir_d} aval={arith.word_to_hex4(aval)}")
    print(f"b={es.ir_d} bval={arith.word_to_hex4(bval)}")

    common.mode.devlog("User trap: interrupt")
    i = 3
    common.mode.devlog(f"\n*** Interrupt {i} ***")
    es.rpc.put(es.pc.get())
    es.rstat.put(es.status_reg.get())
    es.iir.put(es.ir.get())
    es.iadr.put(es.adr.get())
    arch.clear_bit_in_reg_le(es.req, i)
    es.pc.put(limit_address(es, es.vect.get() + 2 * i))
    es.status_reg.put(es.status_reg.get() & \
                       arch.mask_to_clear_bit_le(arch.int_enable_bit) & \
                       arch.mask_to_clear_bit_le(arch.user_state_bit))
    return

def trap_read(es):
    common.mode.devlog('trap_read')
    # For CLI, read from stdin
    input_str = input() # Read a line from stdin
    
    a = es.regfile[es.ir_a].get() # buffer address
    b = es.regfile[es.ir_b].get() # buffer size
    
    # Convert input string to character codes and store in memory
    chars_read = 0
    for char_code in input_str[:b]: # Read up to 'b' characters
        es.ab.write_mem16(es, a + chars_read, ord(char_code))
        chars_read += 1
    
    es.regfile[es.ir_a].put(a + chars_read) # Address after last word stored
    es.regfile[es.ir_b].put(chars_read) # Number of characters read
    
    es.io_log_buffer += common.highlight_field(input_str[:chars_read], "READ")
    refresh_io_log_buffer(es)

def trap_write(es):
    common.mode.devlog('trap_write')
    a = es.regfile[es.ir_a].get() # buffer address
    b = es.regfile[es.ir_b].get() # buffer size
    
    output_str = ""
    for i in range(b):
        output_str += chr(mem_fetch_data(es, a + i))
    
    es.io_log_buffer += output_str
    refresh_io_log_buffer(es)

def refresh_io_log_buffer(es):
    # For CLI, simply print the buffer
    print(f"IO Log: {es.io_log_buffer}")

def handle_rx(es):
    common.mode.devlog(f"handle rx secondary={es.ir_b}")
    es.instr_fmt_str = "RX"
    dispatch_rx[es.ir_b](es)

def handle_exp(es):
    es.instr_fmt_str = "EXP"
    code = 16 * es.ir_a + es.ir_b
    if code < limit_exp_code:
        common.mode.devlog(f"dispatching EXP code={code} d={es.ir_d}")
        dispatch_exp[code](es)
    else:
        common.mode.devlog(f"EXP bad code {arith.word_to_hex4(code)}")

def exp2_push(es):
    x = es.regfile[es.ir_d].get()
    re = es.field_e
    top = es.regfile[re].get()
    limit = es.regfile[es.field_f].get()
    print(f"push x={x} re={re} top={top} limit={limit}")
    if top < limit:
        top += 1
        es.regfile[re].put(top)
        mem_store(es, top, x)
    else:
        print("push: stack overflow")
        es.regfile[15].put(0)
        arch.set_bit_in_reg_le(es.regfile[15], arch.bit_ccS)
        arch.set_bit_in_reg_le(es.req, arch.stack_overflow_bit)

def exp2_pop(es):
    re = es.field_e
    top = es.regfile[re].get()
    base = es.regfile[es.field_f].get()
    if top >= base:
        es.regfile[es.ir_d].put(mem_fetch_data(es, top))
        top -= 1
        es.regfile[es.field_e].put(top)
    else:
        print("pop: stack underflow")
        es.regfile[15].put(0)
        arch.set_bit_in_reg_le(es.regfile[15], arch.bit_ccs)
        arch.set_bit_in_reg_le(es.req, arch.stack_underflow_bit)

def exp2_top(es):
    a = es.regfile[es.ir_a].get()
    b = es.regfile[es.ir_b].get()
    if a >= b:
        es.regfile[es.ir_d].put(mem_fetch_data(es, a))
    else:
        common.mode.devlog("pop: stack underflow")
        # arith.set_bit_in_reg_le(es.req, arch.stack_underflow_bit) # req is not a register

dispatch_primary_opcode = [
    cab_dc(arith.op_add),    # 0
    cab_dc(arith.op_sub),    # 1
    cab_dc(arith.op_mul),    # 2
    cab_dc(arith.op_div),    # 3
    ab_c(arith.op_cmp),      # 4
    cab_dc(arith.op_addc),   # 5
    cab_dc(arith.op_muln),   # 6
    cab_dca(arith.op_divn),  # 7
    nop,                     # 8
    nop,                     # 9
    nop,                     # a
    nop,                     # b
    op_trap,                 # c
    nop,                     # d
    handle_exp,              # e
    handle_rx                # f
]

def rx(f):
    def inner(es):
        common.mode.devlog('rx')
        es.instr_op_str = arch.mnemonicRX[es.ir_b]
        es.instr_disp = mem_fetch_instr(es, es.pc.get())
        es.next_instr_addr = arith.bin_add(es.next_instr_addr, 1)
        es.pc.put(limit_address(es, es.next_instr_addr))
        es.ab.write_scb(es, es.ab.SCB_NEXT_INSTR_ADDR, es.next_instr_addr)
        es.ea = arith.bin_add(es.regfile[es.ir_a].get(), es.instr_disp)
        es.instr_ea = es.ea
        es.adr.put(es.instr_ea)
        common.mode.devlog(f"rx ea, disp={arith.word_to_hex4(es.instr_disp)}")
        common.mode.devlog(f"rx ea, idx={arith.word_to_hex4(es.regfile[es.ir_a].get())}")
        common.mode.devlog(f"rx ea = {arith.word_to_hex4(es.ea)}")
        f(es)
    return inner

def rx_lea(es):
    es.regfile[es.ir_d].put(es.ea)

def rx_load(es):
    common.mode.devlog('rx_load')
    es.regfile[es.ir_d].put(arith.limit16(mem_fetch_data(es, es.ea)))

def rx_store(es):
    common.mode.devlog('rx_store')
    x = es.regfile[es.ir_d].get()
    mem_store(es, es.ea, arith.limit16(x))

def rx_jump(es):
    common.mode.devlog('rx_jump')
    es.next_instr_addr = es.ea
    es.pc.put(limit_address(es, es.next_instr_addr))

def rx_jumpc0(es):
    common.mode.devlog('rx_jumpc0')
    cc = es.regfile[15].get()
    if arch.get_bit_in_word_le(cc, es.ir_d) == 0:
        es.next_instr_addr = es.ea
        es.pc.put(limit_address(es, es.next_instr_addr))

def rx_jumpc1(es):
    common.mode.devlog('rx_jumpc1')
    cc = es.regfile[15].get()
    if arch.get_bit_in_word_le(cc, es.ir_d) == 1:
        es.next_instr_addr = es.ea
        es.pc.put(limit_address(es, es.next_instr_addr))

def rx_jumpz(es):
    common.mode.devlog('rx_jumpz')
    if es.regfile[es.ir_d].get() == 0:
        es.next_instr_addr = es.ea
        es.pc.put(limit_address(es, es.next_instr_addr))

def rx_jumpnz(es):
    common.mode.devlog('rx_jumpnz')
    if es.regfile[es.ir_d].get() != 0:
        es.next_instr_addr = es.ea
        es.pc.put(limit_address(es, es.next_instr_addr))

def rx_testset(es):
    common.mode.devlog('testset')
    es.regfile[es.ir_d].put(mem_fetch_data(es, es.ea))
    mem_store(es, es.ea, 1)

def rx_jal(es):
    common.mode.devlog('rx_jal')
    es.regfile[es.ir_d].put(es.pc.get())
    es.next_instr_addr = es.ea
    es.pc.put(limit_address(es, es.next_instr_addr))

def rx_nop(es):
    common.mode.devlog('rx_nop')

dispatch_rx = [
    rx(rx_lea),       # 0
    rx(rx_load),      # 1
    rx(rx_store),     # 2
    rx(rx_jump),      # 3
    rx(rx_jumpc0),    # 4
    rx(rx_jumpc1),    # 5
    rx(rx_jal),       # 6
    rx(rx_jumpz),     # 7
    rx(rx_jumpnz),    # 8
    rx(rx_testset),   # 9
    rx(rx_nop),       # a (placeholder for leal)
    rx(rx_nop),       # b (placeholder for loadl)
    rx(rx_nop),       # c (placeholder for storel)
    rx(rx_nop),       # d
    rx(rx_nop),       # e
    rx(rx_nop)        # f
]

def exp2(f):
    def inner(es):
        common.mode.devlog('>>> EXP instruction')
        exp_code = 16 * es.ir_a + es.ir_b
        es.instr_op_str = arch.mnemonicEXP[exp_code]
        es.instr_disp = mem_fetch_instr(es, es.pc.get())
        es.adr.put(es.instr_disp)
        es.next_instr_addr = arith.bin_add(es.next_instr_addr, 1)
        es.pc.put(limit_address(es, es.next_instr_addr))
        es.ab.write_scb(es, es.ab.SCB_NEXT_INSTR_ADDR, es.next_instr_addr)
        temp_instr = es.instr_disp
        es.field_gh = temp_instr & 0x00FF
        es.field_h = temp_instr & 0x000F
        temp_instr >>= 4
        es.field_g = temp_instr & 0x000F
        temp_instr >>= 4
        es.field_f = temp_instr & 0x000F
        temp_instr >>= 4
        es.field_e = temp_instr & 0x000F
        f(es)
    return inner

def exp2_nop(es):
    common.mode.devlog('exp2_nop')

def exp2_brf(es):
    common.mode.devlog('exp_brf')
    es.pc.put(limit_address(es, es.pc.get() + es.adr.get()))

def exp2_brb(es):
    common.mode.devlog('exp_brb')
    es.pc.put(limit_address(es, es.pc.get() - es.adr.get()))

def exp2_brfz(es):
    common.mode.devlog('exp_brf')
    x = es.regfile[es.ir_d].get()
    if x == 0:
        es.pc.put(limit_address(es, es.pc.get() + es.adr.get()))
        print("brfz is branching")
    else:
        print("brfz is not branching")

def exp2_brbz(es):
    common.mode.devlog('exp_brb')
    x = es.regfile[es.ir_d].get()
    if x == 0:
        es.pc.put(limit_address(es, es.pc.get() - es.adr.get()))
        print("brbz is branching")
    else:
        print("brbz is not branching")

def exp2_brfnz(es):
    common.mode.devlog('exp_brfnz')
    x = es.regfile[es.ir_d].get()
    if x != 0:
        es.pc.put(limit_address(es, es.pc.get() + es.adr.get()))
        print("brfnz is branching")
    else:
        print("brfnz is not branching")

def exp2_brbnz(es):
    common.mode.devlog('exp_brbnz')
    x = es.regfile[es.ir_d].get()
    if x != 0:
        es.pc.put(limit_address(es, es.pc.get() - es.adr.get()))
        print("brbnz is branching")
    else:
        print("brbnz is not branching")

def exp2_brfc0(es):
    common.mode.devlog('exp_brfc0')
    x = es.regfile[es.ir_d].get()
    bit_idx = es.field_e
    b = arch.get_bit_in_word_le(x, bit_idx)
    offset = es.instr_disp & 0x0FFF
    print(f"brfc0 x={x} bit_idx={bit_idx} b={b}")
    if b == 0:
        es.pc.put(limit_address(es, es.pc.get() + offset))
        print("brfc0 is branching")
    else:
        print("brfc0 is not branching")

def exp2_brbc0(es):
    common.mode.devlog('exp_brbc0')
    x = es.regfile[es.ir_d].get()
    bit_idx = es.field_e
    b = arch.get_bit_in_word_le(x, bit_idx)
    offset = es.instr_disp & 0x0FFF
    print(f"brbc0 x={x} bit_idx={bit_idx} b={b}")
    if b == 0:
        es.pc.put(limit_address(es, es.pc.get() - offset))
        print("brbc0 is branching")
    else:
        print("brbc0 is not branching")

def exp2_brfc1(es):
    common.mode.devlog('exp_brfc1')
    x = es.regfile[es.ir_d].get()
    bit_idx = es.field_e
    b = arch.get_bit_in_word_le(x, bit_idx)
    offset = es.instr_disp & 0x0FFF
    print(f"brfc1 x={x} bit_idx={bit_idx} b={b}")
    if b != 0:
        es.pc.put(limit_address(es, es.pc.get() + offset))
        print("brfc1 is branching")
    else:
        print("brfc1 is not branching")

def exp2_brbc1(es):
    common.mode.devlog('exp_brbc1')
    x = es.regfile[es.ir_d].get()
    bit_idx = es.field_e
    b = arch.get_bit_in_word_le(x, bit_idx)
    offset = es.instr_disp & 0x0FFF
    if b != 0:
        es.pc.put(limit_address(es, es.pc.get() - offset))
        print("brbc1 is branching")
    else:
        print("brbc1 is not branching")

def exp2_resume(es):
    print('exp2_resume')
    es.status_reg.put(es.rstat.get())
    es.pc.put(limit_address(es, es.rpc.get()))
    es.ir.put(es.iir.get())
    es.adr.put(es.iadr.get())

def exp2_timeron(es):
    print('exp2_timeron')
    x = es.regfile[es.ir_d].get()
    timer_start(es, x)

def exp2_timeroff(es):
    print('exp2_timeroff')
    timer_stop(es)

def exp2_dispatch(es):
    common.mode.devlog('exp_dsptch')
    code = es.regfile[es.ir_d].get()
    limit = es.adr.get()
    here = es.pc.get()
    offset = code if code < limit else limit
    loc = here + offset
    dest = mem_fetch_data(es, loc)
    es.pc.put(limit_address(es, dest))

def exp2_save(es):
    r_start = es.ir_d
    r_end = es.field_e
    index = es.regfile[es.field_f].get()
    offset = es.field_gh
    ea = index + offset
    common.mode.devlog(f"save regs = {r_start}..{r_end} index={index}" \
                       f" offset={offset} ea={arith.word_to_hex4(ea)}")
    sr_looper(lambda a, r: mem_store(es, a, es.regfile[r].get()), ea, r_start, r_end)

def exp2_restore(es):
    common.mode.devlog('exp2_restore')
    r_start = es.ir_d
    r_end = es.field_e
    index = es.regfile[es.field_f].get()
    offset = es.field_gh
    ea = index + offset
    common.mode.devlog(f"restore regs = {r_start}..{r_end} index={index}" \
                       f" offset={offset} ea={arith.word_to_hex4(ea)}")
    sr_looper(lambda a, r: es.regfile[r].put(mem_fetch_data(es, a)), ea, r_start, r_end)

def sr_looper(f, addr, first, last):
    done = False
    r = first
    while not done:
        common.mode.devlog(f"save looper addr={addr} r={r}")
        f(addr, r)
        done = r == last
        addr += 1
        r = bin_inc4(r)

def bin_inc4(x):
    return 0 if x >= 15 else x + 1

def exp2_getctl(es):
    common.mode.devlog('exp2_getctl')
    cregn = es.field_f
    creg_idx = cregn + ctl_reg_index_offset
    common.mode.devlog(f"exp2_getctl cregn={cregn} creg_idx={creg_idx}")
    es.regfile[es.field_e].put(es.register[creg_idx].get())

def exp2_putctl(es):
    common.mode.devlog('putctl')
    cregn = es.field_f
    creg_idx = cregn + ctl_reg_index_offset
    common.mode.devlog(f"putctl src e=={es.field_e} val={es.regfile[es.field_e].get()}")
    common.mode.devlog(f"putctl dest f={es.field_f} cregn={cregn} creg_idx={creg_idx}")
    es.register[creg_idx].put(es.regfile[es.field_e].get())
    es.register[creg_idx].refresh() # Placeholder

def exp2_execute(es):
    common.mode.devlog("exp2_execute")

def exp2_shiftl(es):
    common.mode.devlog(f"shiftl d={arith.word_to_hex4(es.ir_d)}" \
                       f" e={arith.word_to_hex4(es.field_e)}" \
                       f" gh={arith.word_to_hex4(es.field_gh)}")
    x = es.regfile[es.field_e].get()
    k = es.field_gh
    result = arith.shift_l(x, k)
    print(f"shiftl x={arith.word_to_hex4(x)} k={k} result={arith.word_to_hex4(result)}")
    es.regfile[es.ir_d].put(result)

def exp2_shiftr(es):
    common.mode.devlog(f"shiftr d={arith.word_to_hex4(es.ir_d)}" \
                       f" e={arith.word_to_hex4(es.field_e)}" \
                       f" gh={arith.word_to_hex4(es.field_gh)}")
    x = es.regfile[es.field_e].get()
    k = es.field_gh
    result = arith.shift_r(x, k)
    print(f"shiftr x={arith.word_to_hex4(x)} k={k} result={arith.word_to_hex4(result)}")
    es.regfile[es.ir_d].put(result)

def exp2_extract(es):
    print('exp2_extract')
    d_old = es.regfile[es.ir_d].get()
    src = es.regfile[es.field_e].get()
    dest_right = es.field_f
    src_right = es.field_g
    src_left = es.field_h
    d_new = arith.calculate_extract(16, 0xFFFF, d_old, src,\
                                    dest_right,\
                                    src_right, src_left)
    print(f"extract " \
          f" d_old = {arith.word_to_hex4(d_old)}" \
          f" src = {arith.word_to_hex4(src)}" \
          f" dest_right = {dest_right}" \
          f" src_right = {src_right}" \
          f" src_left = {src_left}" \
          f" d_new = {arith.word_to_hex4(d_new)}")
    es.regfile[es.ir_d].put(d_new)

def exp2_logicf(es):
    common.mode.devlog('EXP logicf')
    print("************* logicf")
    x = es.regfile[es.ir_d].get()
    y = es.regfile[es.field_e].get()
    idx1 = es.field_f
    idx2 = es.field_g
    fcn = es.field_h
    result = arith.apply_logic_fcn_field(fcn, x, y, idx1, idx2)
    print(f"logicf x={arith.word_to_hex4(x)} y={arith.word_to_hex4(y)} result={arith.word_to_hex4(result)}")
    es.regfile[es.ir_d].put(result)

def exp2_logicb(es):
    common.mode.devlog('EXP logicb')
    w1 = es.regfile[es.ir_d].get()
    w2 = es.regfile[es.field_e].get()
    x = arch.get_bit_in_word_le(w1, es.field_f)
    y = arch.get_bit_in_word_le(w2, es.field_g)
    fcn = es.field_h
    bresult = arith.apply_logic_fcn_bit(fcn, x, y)
    wresult = arch.put_bit_in_word_le(16, w1, es.field_f, bresult)
    print(f"logicb w1={arith.word_to_hex4(w1)} x={x} y={y} fcn={fcn} bresult={bresult} wresult={arith.word_to_hex4(wresult)}")
    es.regfile[es.ir_d].put(wresult)

def exp2_logicu(es):
    common.mode.devlog('EXP logicu')
    regx = es.regfile[es.ir_d].get()
    bitx = arith.extract_bit(regx, es.field_e)
    regy = es.regfile[es.field_f].get()
    bity = arith.extract_bit(regy, es.field_g)
    fcn = es.field_h
    bresult = arith.apply_logic_fcn_bit(fcn, bitx, bity)
    wresult = arith.set_bit(regx, es.field_e, bresult)
    es.regfile[es.ir_d].put(wresult)

def exp2_brc0(es):
    common.mode.devlog('exp_brc0')
    x = es.regfile[es.ir_d].get()
    bit_idx = es.field_e
    b = arch.get_bit_in_word_le(x, bit_idx)
    offset = es.instr_disp & 0x0FFF
    print(f"brfc0 x={x} bit_idx={bit_idx} b={b}")
    if b == 0:
        es.pc.put(limit_address(es, es.pc.get() + offset))
        print("brfc0 is branching")
    else:
        print("brfc0 is not branching")

def exp2_brc1(es):
    common.mode.devlog('exp_brc1')
    x = es.regfile[es.ir_d].get()
    bit_idx = es.field_e
    b = arch.get_bit_in_word_le(x, bit_idx)
    offset = es.instr_disp & 0x0FFF
    print(f"brfc0 x={x} bit_idx={bit_idx} b={b}")
    if b == 0:
        es.pc.put(limit_address(es, es.pc.get() + offset))
        print("brfc0 is branching")
    else:
        print("brfc0 is not branching")

def exp2_brz(es):
    common.mode.devlog('exp_brz')
    x = es.regfile[es.ir_d].get()
    if x == 0:
        es.pc.put(limit_address(es, es.pc.get() + es.adr.get()))
        print("brfz is branching")
    else:
        print("brfz is not branching")

def exp2_brnz(es):
    common.mode.devlog('exp_brnz')
    x = es.regfile[es.ir_d].get()
    if x == 0:
        es.pc.put(limit_address(es, es.pc.get() + es.adr.get()))
        print("brfz is branching")
    else:
        print("brfz is not branching")

dispatch_exp = [
    exp2(exp2_logicf),   # 00
    exp2(exp2_logicb),   # 01
    exp2(exp2_logicu),   # 02
    exp2(exp2_shiftl),   # 03
    exp2(exp2_shiftr),   # 04
    exp2(exp2_extract),  # 05
    exp2(exp2_nop),      # 06
    exp2(exp2_push),     # 07
    exp2(exp2_pop),      # 08
    exp2(exp2_top),      # 09
    exp2(exp2_save),     # 0a
    exp2(exp2_restore),  # 0b
    exp2(exp2_brc0),     # 0c
    exp2(exp2_brc1),     # 0d
    exp2(exp2_brz),      # 0e
    exp2(exp2_brnz),     # 0f
    exp2(exp2_dispatch), # 10
    exp2(exp2_getctl),   # 11
    exp2(exp2_putctl),   # 12
    exp2(exp2_resume),   # 13
    exp2(exp2_timeron),  # 14
    exp2(exp2_timeroff), # 15
    exp2(exp2_add32)     # 16
]

limit_exp_code = len(dispatch_exp)

# -------------------------------------------------------------------------
# New functions for loading and booting
# -------------------------------------------------------------------------

def parse_copy_object_module_to_memory(es, om):
    common.mode.devlog(f"parse_copy_object_module_to_memory {om.mod_name}")
    current_address = 0
    for x in om.obj_lines:
        fields = st.parse_obj_line(x)
        if fields["operation"] == "data":
            for val_str in fields["operands"]:
                val = arith.hex4_to_word(val_str)
                es.ab.write_mem16(es, current_address, val)
                current_address += 1
        elif fields["operation"] == "org":
            current_address = arith.hex4_to_word(fields["operands"][0])
        elif fields["operation"] == "module":
            pass # ignore
        elif fields["operation"] == "relocate":
            pass # ignore, already handled by linker
        elif fields["operation"] == "import":
            pass # ignore, already handled by linker
        elif fields["operation"] == "export":
            pass # ignore, already handled by linker
        else:
            common.mode.devlog(f"parse_copy_object_module_to_memory: unknown operation {fields["operation"]}")

def boot(es, obj_md):
    common.mode.devlog('em.boot')
    proc_reset(es) # Reset processor state
    
    # Load the object module into memory
    parse_copy_object_module_to_memory(es, obj_md)
    
    es.ab.write_scb(es, es.ab.SCB_STATUS, es.ab.SCB_READY)
    es.pc.put(0) # Set program counter to 0
    es.next_instr_addr = 0
    es.cur_instr_addr = 0
    # gui.init_listing(es) # GUI function, not needed for CLI

# -------------------------------------------------------------------------
# Debugging/Output functions
# -------------------------------------------------------------------------

def dump_registers(es):
    print("\n--- Registers ---")
    # Print general purpose registers (R0-R15)
    for i in range(16):
        reg = es.regfile[i]
        print(f"{reg.reg_name}: {arith.word_to_hex4(reg.get())} ({reg.get()})")

    # Print control registers
    print("\n--- Control Registers ---")
    control_reg_names = {
        'pc': 'Program Counter', 'ir': 'Instruction Register',
        'adr': 'Address Register', 'dat': 'Data Register',
        'status_reg': 'Status Register', 'mask': 'Mask Register',
        'req': 'Request Register', 'rstat': 'Return Status Register',
        'rpc': 'Return Program Counter', 'iir': 'Interrupt Instruction Register',
        'iadr': 'Interrupt Address Register', 'vect': 'Vector Register',
        'bpseg': 'Base Program Segment', 'epseg': 'End Program Segment',
        'bdseg': 'Base Data Segment', 'edseg': 'End Data Segment'
    }
    for reg in es.control_registers:
        if reg.reg_name in control_reg_names:
            print(f"{control_reg_names[reg.reg_name]} ({reg.reg_name}): {arith.word_to_hex4(reg.get())} ({reg.get()})")
    print("-----------------")

def dump_memory(es, start_addr=0, end_addr=arch.mem_size):
    print(f"\n--- Memory (Addresses {arith.word_to_hex4(start_addr)} to {arith.word_to_hex4(end_addr-1)}) ---")
    
    current_addr = start_addr
    while current_addr < end_addr:
        line_output = f"MEM[{arith.word_to_hex4(current_addr)}]: "
        for i in range(arch.words_per_line):
            if current_addr + i < end_addr:
                value = es.ab.read_mem16(es, current_addr + i)
                line_output += f"{arith.word_to_hex4(value)} "
            else:
                break
        print(line_output)
        current_addr += arch.words_per_line
    print("-----------------")

def dump_modified_registers_summary(es):
    # Use a dictionary to store the last modified value for each register
    modified_regs = {}
    for reg_num, value in es.copyable["regStored"]:
        modified_regs[reg_num] = value

    if not modified_regs:
        print("\n--- No Registers Modified ---")
        return

    print("\n--- Modified Registers Summary ---")
    # Sort by register number for consistent output
    sorted_reg_nums = sorted(modified_regs.keys())

    for reg_num in sorted_reg_nums:
        reg = es.register[reg_num]
        reg_name = reg.reg_name
        reg_value = modified_regs[reg_num]
        print(f"{reg_name}: {arith.word_to_hex4(reg_value)} ({reg_value})")
    print("--------------------------------")

def dump_accessed_memory_summary(es):
    # Extract only addresses from the logs
    all_accessed_tuples = es.copyable["memFetchInstrLog"] + es.copyable["memFetchDataLog"] + es.copyable["memStoreLog"]
    accessed_addresses = sorted(list(set([addr for addr, _ in all_accessed_tuples])))

    if not accessed_addresses:
        print("\n--- No Memory Accessed ---")
        return

    print("\n--- Accessed Memory Summary ---")

    # Group contiguous addresses
    grouped_addresses = []
    if accessed_addresses:
        current_group = [accessed_addresses[0]]
        for i in range(1, len(accessed_addresses)):
            if accessed_addresses[i] == current_group[-1] + 1:
                current_group.append(accessed_addresses[i])
            else:
                grouped_addresses.append(current_group)
                current_group = [accessed_addresses[i]]
        grouped_addresses.append(current_group) # Add the last group

    for group in grouped_addresses:
        start_addr = group[0]
        end_addr = group[-1]
        
        # Print header for the block
        print(f"Addresses {arith.word_to_hex4(start_addr)} to {arith.word_to_hex4(end_addr)}:")
        
        # Print memory content in lines of arch.words_per_line
        current_line_start = start_addr
        while current_line_start <= end_addr:
            line_output = f"  MEM[{arith.word_to_hex4(current_line_start)}]: "
            for i in range(arch.words_per_line):
                addr_to_print = current_line_start + i
                if addr_to_print <= end_addr:
                    value = es.ab.read_mem16(es, addr_to_print) # Re-read to get final value
                    line_output += f"{arith.word_to_hex4(value)} "
                else:
                    break
            print(line_output)
            current_line_start += arch.words_per_line
    print("-----------------------------")