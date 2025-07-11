# SigmaPy is a Sigma16 port in Python 
## About Sigma16(https://github.com/jtod/Sigma16)
Sigma16 is a computer architecture designed for research and teaching in computer systems. This application provides a complete environment for experimenting with the architecture, including an editor, assembler, linker, emulator, and an integrated development environment (IDE) with a graphical user interface.


Yeah cool basically yoinked it from the original repo https://github.com/jtod/Sigma16 and rewrote the functionality in python as a CLI and GUI because the site just looks a bit ucky on my Arch Linux setup (yes, I use arch ) (the 😎 is supposed to be the sunglasses emoji but it looks like a ? to me because I’m on arch) (I use arch btw).

Anyway… python main.py run yourassemblycode.asm.txt basically it for the CLI and the GUI should be self explanatory. Setup/documentation beneath.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/kianacaster/SigmaPy/
    cd sigma16_ide_python
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

### IDE Usage (Graphical User Interface)

To run the graphical IDE:

```bash
python src/main.py
```

The IDE provides a comprehensive environment for developing and testing Sigma16 assembly programs. Key features include:

*   **Code Editor:** The primary area for writing your assembly code. Text wrapping has been disabled for better readability, and the font size has been adjusted.
*   **I/O Log:** Located directly beneath the Code Editor, this section displays output from the assembler and emulator, including any errors or messages. Its width is synchronized with the Code Editor for a consistent layout.
*   **Registers and Memory Views:** Positioned horizontally above the Machine View, these sections provide a clear, readable display of the CPU's registers and memory contents. They are set to a fixed height to ensure optimal readability and prevent unwanted stretching.
*   **Machine View:** A visual representation of the Sigma16 CPU, showing its internal state during program execution.
*   **Toolbar:** Provides quick access to essential actions, including:
    *   **Run:** Executes the loaded assembly program.
    *   **Pause:** Pauses the execution of the program.
    *   **Step:** Executes the program one instruction at a time. **Note: The "Step" button is currently not working as expected.**
    *   **Reset:** Resets the emulator to its initial state.
    *   **Open:** Loads an assembly file into the editor.
    *   **Save:** Saves the current assembly code to a file.

### CLI Usage (Command Line Interface)

Usage

The Sigma16 CLI tool allows you to assemble and run Sigma16 assembly files.

Running the Tool

You can execute the tool using `python3 src/main.py` followed by a command and its arguments.

Commands

`assemble`

Assembles a Sigma16 assembly file and displays the assembly results, including any errors.

Syntax:

```
python3 src/main.py assemble <file_path>
```

`<file_path>`: The path to your Sigma16 assembly file (e.g., `hello.asm.txt`).
Example:

```
python3 src/main.py assemble hello.asm.txt
```

Output:

*   Indicates if assembly was successful or if errors occurred.
*   Lists assembly errors if any.

`run`

Assembles and then executes a Sigma16 assembly file in the emulator. By default, it provides a concise summary of the program’s execution, including modified registers and accessed memory locations.

Syntax:

```
python3 src/main.py run <file_path> [options]
```

`<file_path>`: The path to your Sigma16 assembly file (e.g., `hello.asm.txt`).
Options:

*   `--mem-dump`: Dumps the entire memory content after execution.
*   `--reg-dump`: Dumps the state of all registers after execution.
*   `--verbose`: Enables verbose debug logging during emulation. This will show detailed internal emulator operations.

Examples:

Run with default summary output:
```
python3 src/main.py run ../Examples/Core/Arithmetic/Mult.asm.txt
```

Output:

*   Assembly success/failure message.
*   “Running Emulator” message.
*   Any output from `trap_read` or `trap_write` instructions in your assembly program.
*   “Emulator halted.” or “Emulator stopped…” message.
*   “Modified Registers Summary”: Lists only the registers whose values changed during execution, showing their final hexadecimal and decimal values.
*   “Accessed Memory Summary”: Lists memory addresses that were read from or written to, showing their final hexadecimal values. Addresses are grouped for readability.

Run with full memory and register dumps:
```
python3 src/main.py run hello.asm.txt --mem-dump --reg-dump
```

Output:

*   Same as default summary, plus:
*   A detailed dump of all registers.
*   A detailed dump of the entire memory space.

Run with verbose debug logging (for development/debugging):
```
python3 src/main.py run hello.asm.txt --verbose
```

Output:

*   Includes all `common.mode.devlog` messages, providing extensive detail about each step of the emulation process. This output can be very long.
