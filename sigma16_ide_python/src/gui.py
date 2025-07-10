import sys
import time
import threading
from PySide6.QtCore import Qt, QObject, Signal, QThread, QMutex, QWaitCondition
from PySide6.QtGui import QFont, QAction, QIcon, QColor, QTextCharFormat, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
    QTableView, QHeaderView, QSplitter, QGroupBox, QDockWidget, QFileDialog, QToolBar
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

import common
import assembler
import emulator
import arrbuf
import state
import architecture as arch
from machine_view import MachineView

class RegisterModel(QStandardItemModel):
    def __init__(self, emulator_state):
        super().__init__(16, 2)
        self.es = emulator_state
        self.setHorizontalHeaderLabels(["Register", "Value"])
        self.previous_values = {} # To store previous register values for highlighting

    def update(self):
        for i in range(16):
            reg_name = f"R{i}"
            # Ensure we read the value in a thread-safe way if needed, though direct access is often fine for reads
            value = self.es.regfile[i].get()
            current_item = QStandardItem(reg_name)
            value_item = QStandardItem(f"0x{value:04X}")

            # Check if value has changed for highlighting
            if reg_name in self.previous_values and self.previous_values[reg_name] != value:
                value_item.setBackground(Qt.GlobalColor.yellow) # Highlight changed registers
            
            self.setItem(i, 0, current_item)
            self.setItem(i, 1, value_item)
            self.previous_values[reg_name] = value # Update previous value

class MemoryModel(QStandardItemModel):
    def __init__(self, emulator_state):
        super().__init__(256, 17)
        self.es = emulator_state
        header_labels = ["Address"] + [f"+{i:X}" for i in range(16)]
        self.setHorizontalHeaderLabels(header_labels)

    def update(self):
        for row in range(256):
            address = row * 16
            address_item = QStandardItem(f"0x{address:04X}")
            self.setItem(row, 0, address_item)
            for col in range(16):
                value = self.es.ab.read_mem16(self.es, address + col)
                self.setItem(row, col + 1, QStandardItem(f"0x{value:04X}"))

class EmulatorWorker(QObject):
    instruction_executed = Signal()
    execution_finished = Signal(str)
    execution_paused = Signal() # Emitted when execution pauses (e.g., after a step)

    def __init__(self, emulator_state):
        super().__init__()
        self.es = emulator_state
        self._run_continuous = False
        self._step_once = False
        self._stop_requested = False
        self._mutex = QMutex()
        self._wait_condition = QWaitCondition()

    def run(self):
        self._stop_requested = False
        while not self._stop_requested:
            self._mutex.lock()
            try:
                print(f"EmulatorWorker.run: Loop start. _run_continuous={self._run_continuous}, _step_once={self._step_once}, _stop_requested={self._stop_requested}")
                # Determine action based on flags
                if self._run_continuous:
                    action = "continuous"
                elif self._step_once:
                    action = "step"
                else:
                    action = "wait"

                print(f"EmulatorWorker.run: Determined action={action}")

                if action == "wait":
                    print("EmulatorWorker.run: Entering wait state...")
                    self._wait_condition.wait(self._mutex) # Wait until signaled
                    print("EmulatorWorker.run: Woke up from wait.")
                    # After waking up, re-evaluate action
                    if self._stop_requested: # Check if stop was requested while waiting
                        print("EmulatorWorker.run: Stop requested while waiting. Breaking loop.")
                        break
                    if self._run_continuous:
                        action = "continuous"
                    elif self._step_once:
                        action = "step"
                    else: # Spurious wakeup or no action requested
                        print("EmulatorWorker.run: Spurious wakeup or no action. Continuing to wait.")
                        continue # Go back to waiting

                status = self.es.ab.read_scb(self.es, self.es.ab.SCB_STATUS)
                print(f"EmulatorWorker.run: After action determination. Status={status}")
                if status in [self.es.ab.SCB_HALTED, self.es.ab.SCB_BREAK]:
                    print(f"EmulatorWorker.run: Execution finished. Status={status}. Setting _stop_requested=True.")
                    self.execution_finished.emit("Execution halted." if status == self.es.ab.SCB_HALTED else "Breakpoint reached.")
                    self._stop_requested = True
                    break

                if action == "continuous":
                    emulator.execute_instruction(self.es)
                    if self._stop_requested: break # Check stop request immediately after execution
                    self.instruction_executed.emit()
                    time.sleep(0.05)
                    if self._stop_requested: break # Check stop request immediately after sleep
                elif action == "step":
                    emulator.execute_instruction(self.es)
                    if self._stop_requested: break # Check stop request immediately after execution
                    self.instruction_executed.emit()
                    self._step_once = False # Reset flag after one step
                    self._run_continuous = False # Ensure continuous is off after a step
                    self.execution_paused.emit()
            finally:
                self._mutex.unlock()
                print("EmulatorWorker.run: Mutex unlocked.")

    def start_continuous(self):
        self._mutex.lock()
        try:
            self._run_continuous = True
            self._step_once = False
            self._wait_condition.wakeAll() # Wake up the worker
        finally:
            self._mutex.unlock()

    def start_step(self):
        self._mutex.lock()
        try:
            self._step_once = True
            self._run_continuous = False
            self._wait_condition.wakeAll() # Wake up the worker
        finally:
            self._mutex.unlock()

    def stop(self):
        self._mutex.lock()
        try:
            self._stop_requested = True
            self._run_continuous = False
            self._step_once = False
            self._wait_condition.wakeAll() # Wake up to allow it to exit
        finally:
            self._mutex.unlock()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sigma16 IDE")
        self.setGeometry(100, 100, 1400, 900)
        self.showFullScreen() # Start in fullscreen by default

        self.es = emulator.EmulatorState(common.ES_gui_thread, arrbuf)
        self.setDockNestingEnabled(True)

        # Create main horizontal splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)

        # Left-side vertical splitter (Code Editor and I/O Log)
        left_vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(left_vertical_splitter)

        # Code Editor (left pane)
        self.code_editor = QTextEdit() # Initialize code_editor
        self.code_editor.setWordWrapMode(QTextOption.NoWrap)
        self.code_dock = QDockWidget("Code Editor", self)
        self.code_dock.setWidget(self.code_editor)
        left_vertical_splitter.addWidget(self.code_dock)

        # I/O Log (bottom-left pane)
        io_group = QGroupBox("I/O Log")
        io_layout = QVBoxLayout(io_group)
        self.io_log = QTextEdit()
        self.io_log.setReadOnly(True)
        io_layout.addWidget(self.io_log)
        left_vertical_splitter.addWidget(io_group)

        # Set stretch factors for left_vertical_splitter
        left_vertical_splitter.setStretchFactor(0, 3) # Code Editor gets 75% of space
        left_vertical_splitter.setStretchFactor(1, 1) # I/O Log gets 25% of space

        # Right-side vertical splitter
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(right_splitter)

        # Registers and Memory horizontal splitter
        reg_mem_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Registers view
        reg_group = QGroupBox("Registers")
        reg_layout = QVBoxLayout(reg_group)
        self.reg_view = QTableView()
        self.reg_model = RegisterModel(self.es)
        self.reg_view.setModel(self.reg_model)
        self.reg_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        reg_layout.addWidget(self.reg_view)
        
        reg_mem_splitter.addWidget(reg_group)
        

        # Memory view
        mem_group = QGroupBox("Memory")
        mem_layout = QVBoxLayout(mem_group)
        self.mem_view = QTableView()
        self.mem_model = MemoryModel(self.es)
        self.mem_view.setModel(self.mem_model)
        self.mem_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        mem_layout.addWidget(self.mem_view)
        
        reg_mem_splitter.addWidget(mem_group)
        reg_mem_splitter.setFixedHeight(250) # Fixed height for the combined registers and memory section
        
        
        right_splitter.addWidget(reg_mem_splitter) # Add reg_mem_splitter directly to right_splitter

        # Machine View (top-right pane)
        self.machine_view = MachineView(self.es)
        right_splitter.addWidget(self.machine_view)

        # Set stretch factors for the right_splitter to distribute space
        right_splitter.setStretchFactor(0, 0) # Registers/Memory (fixed height)
        right_splitter.setStretchFactor(1, 1) # MachineView gets remaining space

        # Set stretch factors for the reg_mem_splitter
        reg_mem_splitter.setStretchFactor(0, 1)
        reg_mem_splitter.setStretchFactor(1, 1)

        # Set stretch factors for the main_splitter
        main_splitter.setStretchFactor(0, 1) # Left side (Code Editor + I/O Log)
        main_splitter.setStretchFactor(1, 1) # Right side (Registers/Memory + Machine View)

        # Create Toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)

        # Run Action
        self.run_action = QAction(QIcon.fromTheme("media-playback-start"), "Run", self)
        self.run_action.triggered.connect(self.run_code)
        self.toolbar.addAction(self.run_action)

        # Pause Action
        self.pause_action = QAction(QIcon.fromTheme("media-playback-pause"), "Pause", self)
        self.pause_action.triggered.connect(self.pause_execution)
        self.pause_action.setEnabled(False) # Initially disabled
        self.toolbar.addAction(self.pause_action)

        # Step Action
        self.step_action = QAction(QIcon.fromTheme("media-skip-forward"), "Step", self)
        self.step_action.triggered.connect(self.step_code)
        self.step_action.setEnabled(True) # Initially enabled, can step from start
        self.toolbar.addAction(self.step_action)

        # Reset Action
        self.reset_action = QAction(QIcon.fromTheme("view-refresh"), "Reset", self)
        self.reset_action.triggered.connect(self.reset_emulator)
        self.toolbar.addAction(self.reset_action)

        # File Menu Actions
        file_menu = self.menuBar().addMenu("&File")

        # View Menu Actions
        view_menu = self.menuBar().addMenu("&View")
        self.fullscreen_action = QAction(QIcon.fromTheme("view-fullscreen"), "Fullscreen", self)
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(self.fullscreen_action)
        open_action = QAction(QIcon.fromTheme("document-open"), "Open...", self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        save_action = QAction(QIcon.fromTheme("document-save"), "Save", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction(QIcon.fromTheme("document-save-as"), "Save As...", self)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)

        # Add file actions to toolbar
        self.toolbar.addAction(open_action)
        self.toolbar.addAction(save_action)

        self.last_asm_info = None # To store asm_info for highlighting
        self.current_file = None # To keep track of the currently open file
        
        # Initialize and start the emulator thread once
        self.emulator_thread = QThread()
        self.emulator_worker = EmulatorWorker(self.es)
        self.emulator_worker.moveToThread(self.emulator_thread)
        self.emulator_thread.started.connect(self.emulator_worker.run)
        self.emulator_worker.instruction_executed.connect(self.update_views)
        self.emulator_worker.execution_finished.connect(self.on_execution_finished)
        self.emulator_worker.execution_paused.connect(self.on_execution_paused)
        self.emulator_thread.start() # Start the worker thread once

        self._assemble_and_boot() # Initialize emulator state and load code
        self.update_views()

    def update_views(self):
        self.reg_model.update()
        self.mem_model.update()
        self._highlight_current_instruction()
        self.machine_view.update_view() # Update the new machine view

    def _assemble_and_boot(self):
        self.io_log.clear()
        source_code = self.code_editor.toPlainText()
        asm_info = assembler.assembler("my_module", source_code)

        if asm_info.n_asm_errors > 0:
            self.io_log.setText(asm_info.md_text)
            self.last_asm_info = None # Clear previous asm_info on error
            return False

        obj_md = state.ObjMd(asm_info.asm_mod_name, asm_info.object_text, asm_info.md_text)
        emulator.boot(self.es, obj_md)
        self.last_asm_info = asm_info # Store for highlighting
        self.update_views() # Show initial state after boot
        return True

    def run_code(self):
        # Always assemble and boot when "Run" is pressed
        if not self._assemble_and_boot():
            return

        self.run_action.setEnabled(False)
        self.pause_action.setEnabled(True)
        self.step_action.setEnabled(False)

        self.emulator_worker.start_continuous() # Tell worker to run continuously

    def pause_execution(self):
        if self.emulator_worker: 
            self.emulator_worker.stop() # Request worker to stop its loop
            # The worker will emit execution_finished or execution_paused
            # which will re-enable buttons

    def step_code(self):
        # Only assemble and boot if the emulator is halted or ready (initial state)
        if self.es.ab.read_scb(self.es, self.es.ab.SCB_STATUS) in [self.es.ab.SCB_HALTED, self.es.ab.SCB_READY]:
            if not self._assemble_and_boot():
                return

        self.run_action.setEnabled(False)
        self.pause_action.setEnabled(False)
        self.step_action.setEnabled(False)

        self.emulator_worker.start_step() # Tell worker to do one step

    def on_execution_finished(self, message):
        self.io_log.append(message)
        self.update_views() # Final update
        self.run_action.setEnabled(True)
        self.pause_action.setEnabled(False)
        self.step_action.setEnabled(True) 
        
        # No need to quit/wait the thread here, it should remain alive

    def on_execution_paused(self):
        self.io_log.append("Execution paused.")
        self.update_views() # Update views after pause
        self.run_action.setEnabled(True)
        self.pause_action.setEnabled(False)
        self.step_action.setEnabled(True) 

    def reset_emulator(self):
        # Stop the worker if it's running continuously
        if self.emulator_worker: # Check if worker exists
            self.emulator_worker.stop() # Request worker to stop its loop
            time.sleep(0.1) # Give a moment for the worker to process the stop request
            self.emulator_thread.quit() # Tell the thread to quit
            self.emulator_thread.wait() # Wait for the thread to finish
            self.emulator_thread = None # Clear reference to old thread
            self.emulator_worker = None # Clear reference to old worker

        # Re-initialize emulator state (registers, memory, etc.)
        emulator.proc_reset(self.es) 
        
        # Re-create the worker and thread for a fresh start
        self.emulator_thread = QThread()
        self.emulator_worker = EmulatorWorker(self.es)
        self.emulator_worker.moveToThread(self.emulator_thread)
        self.emulator_thread.started.connect(self.emulator_worker.run)
        self.emulator_worker.instruction_executed.connect(self.update_views)
        self.emulator_worker.execution_finished.connect(self.on_execution_finished)
        self.emulator_worker.execution_paused.connect(self.on_execution_paused)
        self.emulator_thread.start() # Start the new worker thread

        self._assemble_and_boot() # Re-assemble and boot the code after reset
        self.io_log.clear() # Clear the I/O log
        self.io_log.append("Emulator reset.")
        self.last_asm_info = None # Clear asm_info on reset
        self._clear_highlight() # Clear any line highlighting
        self.update_views() # Update the register and memory views

        # Reset button states
        self.run_action.setEnabled(True)
        self.pause_action.setEnabled(False)
        self.step_action.setEnabled(True)

    def _highlight_current_instruction(self):
        self._clear_highlight() # Clear any existing highlight

        # Ensure es.cur_instr_addr is set and valid
        if hasattr(self.es, 'cur_instr_addr') and self.es.cur_instr_addr is not None:
            if self.last_asm_info:
                # Get the line number from the assembler's metadata
                # The metadata maps the address of the *generated code* to the *source line number*.
                # For directives like 'start:', the address is 0, but the actual instruction is on the next line.
                # We need to ensure we highlight the line of the *executable* instruction.
                
                # Iterate through asm_stmt to find the correct line to highlight
                target_line_number = None
                for stmt in self.last_asm_info.asm_stmt:
                    # Check if the statement's address matches the current instruction address
                    # AND if it's an actual instruction (not a directive that doesn't generate code)
                    if stmt["address"].word == self.es.cur_instr_addr and stmt["operation"]["ifmt"] != arch.iDir:
                        target_line_number = stmt["lineNumber"]
                        break
                
                if target_line_number is not None:
                    format = QTextCharFormat()
                    format.setBackground(QColor(Qt.GlobalColor.darkYellow))

                    cursor = self.code_editor.textCursor()
                    cursor.setPosition(0) # Start from the beginning
                    # Move to the start of the target line
                    cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, target_line_number)
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.MoveAnchor)
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
                    
                    self.code_editor.setTextCursor(cursor)
                    self.code_editor.setCurrentCharFormat(format)
                    # Ensure the highlighted line is visible
                    self.code_editor.ensureCursorVisible()
            
    def _clear_highlight(self):
        format = QTextCharFormat()
        format.setBackground(QColor(Qt.GlobalColor.transparent)) # Or default background color

        cursor = self.code_editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document) # Select entire document
        self.code_editor.setTextCursor(cursor)
        self.code_editor.setCurrentCharFormat(format)
        cursor.clearSelection() # Clear selection after applying format
        self.code_editor.setTextCursor(cursor) # Restore cursor position

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Assembly File", ".", "Assembly Files (*.asm.txt);;All Files (*)")
        if file_name:
            try:
                with open(file_name, 'r') as f:
                    self.code_editor.setText(f.read())
                self.current_file = file_name
                self.setWindowTitle(f"Sigma16 IDE - {file_name}")
                self.io_log.append(f"File loaded: {self.current_file}")
                self.reset_emulator() # Reset emulator state after loading new file
            except Exception as e:
                self.io_log.append(f"Error opening file: {e}")

    def save_file(self):
        if self.current_file:
            try:
                with open(self.current_file, 'w') as f:
                    f.write(self.code_editor.toPlainText())
                self.io_log.append(f"File saved: {self.current_file}")
            except Exception as e:
                self.io_log.append(f"Error saving file: {e}")
        else:
            self.save_file_as()

    def save_file_as(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Assembly File As", ".", "Assembly Files (*.asm.txt);;All Files (*)")
        if file_name:
            try:
                with open(file_name, 'w') as f:
                    f.write(self.code_editor.toPlainText())
                self.current_file = file_name
                self.setWindowTitle(f"Sigma16 IDE - {file_name}")
                self.io_log.append(f"File saved as: {self.current_file}")
            except Exception as e:
                self.io_log.append(f"Error saving file: {e}")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

def start_gui():
    app = QApplication(sys.argv)
    # Apply a modern QSS theme
    app.setStyleSheet("""
    QMainWindow {
        background-color: #1a1a1a; /* Darker background */
        color: #e0e0e0; /* Lighter text for contrast */
    }
    QTextEdit {
        background-color: #2a2a2a; /* Slightly lighter than main window */
        color: #00ff00; /* Green text for code, hi-tech feel */
        border: 1px solid #007acc; /* Blue border for focus */
        padding: 5px;
        font-family: "Consolas", "Monaco", "Courier New", monospace; /* Monospaced font */
        font-size: 10pt;
    }
    QPushButton {
        background-color: #007acc; /* Vibrant blue */
        color: #ffffff;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #005f99; /* Darker blue on hover */
    }
    QPushButton:pressed {
        background-color: #003f66; /* Even darker blue on press */
    }
    QTableView {
        background-color: #2a2a2a;
        color: #e0e0e0;
        border: 1px solid #007acc;
        gridline-color: #444444; /* Subtle grid lines */
        selection-background-color: #007acc;
        selection-color: #ffffff;
    }
    QHeaderView::section {
        background-color: #3a3a3a;
        color: #e0e0e0;
        padding: 4px;
        border: 1px solid #007acc;
        font-weight: bold;
    }
    QGroupBox {
        background-color: #1a1a1a;
        color: #e0e0e0;
        border: 1px solid #007acc;
        border-radius: 4px;
        margin-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 3px;
        color: #00ff00; /* Green title for hi-tech */
        font-weight: bold;
    }
    QDockWidget {
        background-color: #1a1a1a;
        color: #e0e0e0;
        border: 1px solid #007acc;
    }
    QDockWidget::title {
        background-color: #2a2a2a;
        padding: 5px;
        text-align: center;
        color: #e0e0e0;
        font-weight: bold;
    }
    QMenuBar {
        background-color: #2a2a2a;
        color: #e0e0e0;
    }
    QMenuBar::item {
        padding: 5px 10px;
        background-color: transparent;
    }
    QMenuBar::item:selected {
        background-color: #007acc;
    }
    QMenu {
        background-color: #2a2a2a;
        color: #e0e0e0;
        border: 1px solid #007acc;
    }
    QMenu::item {
        padding: 5px 20px;
    }
    QMenu::item:selected {
        background-color: #007acc;
    }
    QToolBar {
        background-color: #2a2a2a;
        border: none;
        padding: 5px;
    }
    QToolButton {
        background-color: transparent;
        border: none;
        padding: 5px;
        color: #e0e0e0;
    }
    QToolButton:hover {
        background-color: #005f99;
        border-radius: 3px;
    }
    QToolButton:pressed {
        background-color: #003f66;
    }
    /* Scrollbar styling for a more modern look */
    QScrollBar:vertical {
        border: 1px solid #444;
        background: #333;
        width: 10px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:vertical {
        background: #007acc;
        min-height: 20px;
        border-radius: 3px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        background: none;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
    QScrollBar:horizontal {
        border: 1px solid #444;
        background: #333;
        height: 10px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:horizontal {
        background: #007acc;
        min-width: 20px;
        border-radius: 3px;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        background: none;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: none;
    }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())