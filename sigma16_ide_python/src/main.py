# main.py

import sys
import os
import argparse
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import common
import assembler
import state
import emulator as em
import arrbuf as ab





def assemble_file(file_path):
    try:
        with open(file_path, 'r') as f:
            src_text = f.read()
        
        base_name = os.path.basename(file_path).split('.')[0]
        
        # Initialize ModuleSet and add a dummy module for assembler to work
        # This is a temporary setup for CLI testing
        state.env.module_set = state.ModuleSet()
        module = state.env.module_set.add_module(base_name, src_text)

        # Run the assembler
        asm_info = assembler.assembler(base_name, src_text)
        module.asm_info = asm_info # Attach asm_info to the module

        if asm_info.n_asm_errors > 0:
            print(f"Assembly completed with {asm_info.n_asm_errors} errors.")
            print("--- Assembly Errors ---")
            # Print errors from metadata
            for line in asm_info.metadata.get_plain_lines():
                if "Error:" in line:
                    print(line)
            print("-----------------------")
        else:
            print("Assembly successful!")
        
        

        return asm_info.obj_md

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during assembly: {e}")
        return None

def run_file(file_path, dump_mem=False, dump_regs=False, verbose=False):
    if verbose:
        common.mode.set_trace()
    obj_md = assemble_file(file_path)
    if not obj_md:
        return

    es = em.EmulatorState(common.ES_gui_thread, ab) # Create an emulator state
    em.boot(es, obj_md)

    print("\n--- Running Emulator ---")
    try:
        # Run instructions until halted or a limit (e.g., 1000 instructions)
        # For now, let's run a fixed number of steps or until halt
        max_instructions = 1000
        for _ in range(max_instructions):
            if es.ab.read_scb(es, es.ab.SCB_STATUS) == es.ab.SCB_HALTED:
                print("Emulator halted.")
                break
            em.execute_instruction(es)
        else:
            print(f"Emulator stopped after {max_instructions} instructions (limit reached).")

    except Exception as e:
        print(f"An error occurred during emulation: {e}")

    print("------------------------")

    # Always show a summary of accessed memory and modified registers
    em.dump_modified_registers_summary(es)
    em.dump_accessed_memory_summary(es)

    if dump_regs:
        em.dump_registers(es)
    if dump_mem:
        em.dump_memory(es)

def main():
    parser = argparse.ArgumentParser(description="Sigma16 IDE CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Assemble command
    assemble_parser = subparsers.add_parser("assemble", help="Assemble a Sigma16 assembly file")
    assemble_parser.add_argument("file", help="Path to the assembly file (.asm.txt)")

    # Run command
    run_parser = subparsers.add_parser("run", help="Assemble and run a Sigma16 assembly file")
    run_parser.add_argument("file", help="Path to the assembly file (.asm.txt)")
    run_parser.add_argument("--mem-dump", action="store_true", help="Dump memory after execution")
    run_parser.add_argument("--reg-dump", action="store_true", help="Dump registers after execution")
    run_parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    if args.command == "assemble":
        assemble_file(args.file)
    elif args.command == "run":
        run_file(args.file, args.mem_dump, args.reg_dump, args.verbose)
        common.mode.clear_trace()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
