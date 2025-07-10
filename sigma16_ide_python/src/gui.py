import sys
import time
import threading
from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtGui import QFont, QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QPushButton, QVBoxLayout, QWidget,
    QTableView, QHeaderView, QSplitter, QGroupBox, QDockWidget, QFileDialog, QToolBar
)
from PySide6.QtGui import QStandardItemModel, QStandardItem

import common
import assembler
import emulator
import arrbuf
import state

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
    # New signal to indicate a pause in continuous execution
    execution_paused = Signal()

    def __init__(self, emulator_state):
        super().__init__()
        self.es = emulator_state
        self._running = False
        self._stepping = False # New flag for stepping mode

    def run(self):
        self._running = True
        status = self.es.ab.read_scb(self.es, self.es.ab.SCB_STATUS)
        
        while self._running and status not in [self.es.ab.SCB_HALTED, self.es.ab.SCB_BREAK]:
            emulator.execute_instruction(self.es)
            self.instruction_executed.emit()
            status = self.es.ab.read_scb(self.es, self.es.ab.SCB_STATUS)

            if self._stepping: # If in stepping mode, execute one and stop
                self._running = False
                self.execution_paused.emit() # Indicate pause after single step
                break
            
            time.sleep(0.05) # Small delay for visualization

        if status == self.es.ab.SCB_HALTED:
            self.execution_finished.emit("Execution halted.")
        elif status == self.es.ab.SCB_BREAK:
            self.execution_finished.emit("Breakpoint reached.")
        elif self._stepping: # If it stopped because of stepping
            pass # Handled by execution_paused
        else:
            self.execution_finished.emit("Execution stopped.")

    def stop(self):
        self._running = False

    def step(self):
        self._stepping = True
        self._running = True # Ensure run loop starts
        self.run() # Call run to execute one instruction

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sigma16 IDE")
        self.setGeometry(100, 100, 1400, 900)

        self.es = emulator.EmulatorState(common.ES_gui_thread, arrbuf)
        self.setDockNestingEnabled(True)

        # Create dockable code editor
        self.code_dock = QDockWidget("Code Editor", self)
        self.code_editor = QTextEdit()
        self.code_editor.setFont(QFont("Courier New", 12))
        self.code_editor.setText(
            """
    module hello
    
    ; Simple program to add two numbers
    
    start:
        lea R1, num1
        lea R2, num2
        load R3, 0[R1]
        load R4, 0[R2]
        add R5, R3, R4
        lea R6, result
        store R5, 0[R6]
        trap R0, R0, R0   ; Halt
        
    num1: data 10
    num2: data 20
    result: reserve 1
    
    end start
"""
        )
        self.code_dock.setWidget(self.code_editor)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.code_dock)

        # Create dockable machine state view
        self.machine_dock = QDockWidget("Machine State", self)
        machine_splitter = QSplitter(Qt.Orientation.Vertical)
        self.machine_dock.setWidget(machine_splitter)

        # Registers view
        reg_group = QGroupBox("Registers")
        reg_layout = QVBoxLayout(reg_group)
        self.reg_view = QTableView()
        self.reg_model = RegisterModel(self.es)
        self.reg_view.setModel(self.reg_model)
        self.reg_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        reg_layout.addWidget(self.reg_view)
        machine_splitter.addWidget(reg_group)

        # Memory view
        mem_group = QGroupBox("Memory")
        mem_layout = QVBoxLayout(mem_group)
        self.mem_view = QTableView()
        self.mem_model = MemoryModel(self.es)
        self.mem_view.setModel(self.mem_model)
        self.mem_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        mem_layout.addWidget(self.mem_view)
        machine_splitter.addWidget(mem_group)
        
        # I/O Log
        io_group = QGroupBox("I/O Log")
        io_layout = QVBoxLayout(io_group)
        self.io_log = QTextEdit()
        self.io_log.setReadOnly(True)
        io_layout.addWidget(self.io_log)
        machine_splitter.addWidget(io_group)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.machine_dock)

        # Central widget for controls (now just a container for the toolbar)
        central_widget = QWidget()
        controls_layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        # Create Toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Run Action
        self.run_action = QAction(QIcon.fromTheme("media-playback-start"), "Run", self)
        self.run_action.triggered.connect(self.run_code)
        toolbar.addAction(self.run_action)

        # Pause Action
        self.pause_action = QAction(QIcon.fromTheme("media-playback-pause"), "Pause", self)
        self.pause_action.triggered.connect(self.pause_execution)
        self.pause_action.setEnabled(False) # Initially disabled
        toolbar.addAction(self.pause_action)

        # Step Action
        self.step_action = QAction(QIcon.fromTheme("media-skip-forward"), "Step", self)
        self.step_action.triggered.connect(self.step_code)
        self.step_action.setEnabled(False) # Initially disabled
        toolbar.addAction(self.step_action)

        # Reset Action
        self.reset_action = QAction(QIcon.fromTheme("view-refresh"), "Reset", self)
        self.reset_action.triggered.connect(self.reset_emulator)
        toolbar.addAction(self.reset_action)

        # File Menu Actions
        file_menu = self.menuBar().addMenu("&File")
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
        toolbar.addAction(open_action)
        toolbar.addAction(save_action)

        # Create View Menu
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.code_dock.toggleViewAction())
        view_menu.addAction(self.machine_dock.toggleViewAction())

        self.current_file = None # To keep track of the currently open file
        self.emulator_thread = None # Reference to the QThread
        self.emulator_worker = None # Reference to the EmulatorWorker

        self.update_views()

    def update_views(self):
        self.reg_model.update()
        self.mem_model.update()

    def _setup_emulator_thread(self):
        if self.emulator_thread and self.emulator_thread.isRunning():
            self.emulator_worker.stop() # Stop any running worker
            self.emulator_thread.quit()
            self.emulator_thread.wait()

        self.emulator_thread = QThread()
        self.emulator_worker = EmulatorWorker(self.es)
        self.emulator_worker.moveToThread(self.emulator_thread)

        self.emulator_thread.started.connect(self.emulator_worker.run)
        self.emulator_worker.instruction_executed.connect(self.update_views)
        self.emulator_worker.execution_finished.connect(self.on_execution_finished)
        self.emulator_worker.execution_paused.connect(self.on_execution_paused)

    def run_code(self):
        self.io_log.clear()
        source_code = self.code_editor.toPlainText()
        asm_info = assembler.assembler("my_module", source_code)

        if asm_info.n_asm_errors > 0:
            self.io_log.setText(asm_info.md_text)
            return

        obj_md = state.ObjMd(asm_info.asm_mod_name, asm_info.object_text, asm_info.md_text)
        emulator.boot(self.es, obj_md)
        self.update_views() # Show initial state after boot

        self.run_action.setEnabled(False)
        self.pause_action.setEnabled(True)
        self.step_action.setEnabled(False) # Disable step when running continuously
        
        self._setup_emulator_thread()
        self.emulator_thread.start()

    def pause_execution(self):
        if self.emulator_worker: # Check if worker exists
            self.emulator_worker.stop()
            # The worker will emit execution_finished or execution_paused
            # which will re-enable buttons

    def step_code(self):
        # Only allow stepping if not currently running continuously
        if not (self.emulator_thread and self.emulator_thread.isRunning()):
            self.io_log.clear() # Clear log for new execution or step
            source_code = self.code_editor.toPlainText()
            asm_info = assembler.assembler("my_module", source_code)

            if asm_info.n_asm_errors > 0:
                self.io_log.setText(asm_info.md_text)
                return

            # If not already booted, boot the emulator
            if self.es.ab.read_scb(self.es, self.es.ab.SCB_STATUS) == self.es.ab.SCB_HALTED or \
               self.es.ab.read_scb(self.es, self.es.ab.SCB_STATUS) == self.es.ab.SCB_READY: # Check if halted or ready
                obj_md = state.ObjMd(asm_info.asm_mod_name, asm_info.object_text, asm_info.md_text)
                emulator.boot(self.es, obj_md)
                self.update_views()

            self.run_action.setEnabled(False)
            self.pause_action.setEnabled(False)
            self.step_action.setEnabled(False)

            self._setup_emulator_thread() # Setup a new thread for stepping
            self.emulator_worker._stepping = True # Set stepping flag
            self.emulator_thread.start() # Start the thread, it will execute one instruction

    def on_execution_finished(self, message):
        self.io_log.append(message)
        self.update_views() # Final update
        self.run_action.setEnabled(True)
        self.pause_action.setEnabled(False)
        self.step_action.setEnabled(True) # Enable step after execution finishes
        
        # Clean up the thread
        if self.emulator_thread:
            self.emulator_thread.quit()
            self.emulator_thread.wait()

    def on_execution_paused(self):
        self.io_log.append("Execution paused.")
        self.update_views() # Update views after pause
        self.run_action.setEnabled(True)
        self.pause_action.setEnabled(False)
        self.step_action.setEnabled(True) # Enable step after pause

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Assembly File", ".", "Assembly Files (*.asm.txt);;All Files (*)")
        if file_name:
            try:
                with open(file_name, 'r') as f:
                    self.code_editor.setText(f.read())
                self.current_file = file_name
                self.setWindowTitle(f"Sigma16 IDE - {file_name}")
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

    def reset_emulator(self):
        # Stop any running emulator thread first
        if self.emulator_thread and self.emulator_thread.isRunning():
            self.emulator_worker.stop()
            self.emulator_thread.quit()
            self.emulator_thread.wait()

        emulator.proc_reset(self.es) # Reset the emulator's internal state
        self.io_log.clear() # Clear the I/O log
        self.io_log.append("Emulator reset.")
        self.update_views() # Update the register and memory views

        # Reset button states
        self.run_action.setEnabled(True)
        self.pause_action.setEnabled(False)
        self.step_action.setEnabled(True)

def start_gui():
    app = QApplication(sys.argv)
    # Apply a modern QSS theme
    app.setStyleSheet("""
    QMainWindow {
        background-color: #2b2b2b;
        color: #f0f0f0;
    }
    QTextEdit {
        background-color: #3c3c3c;
        color: #f0f0f0;
        border: 1px solid #555;
        padding: 5px;
    }
    QPushButton {
        background-color: #007acc;
        color: #ffffff;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
    }
    QPushButton:hover {
        background-color: #005f99;
    }
    QTableView {
        background-color: #3c3c3c;
        color: #f0f0f0;
        border: 1px solid #555;
        gridline-color: #555;
        selection-background-color: #007acc;
    }
    QHeaderView::section {
        background-color: #4a4a4a;
        color: #f0f0f0;
        padding: 4px;
        border: 1px solid #555;
    }
    QGroupBox {
        background-color: #2b2b2b;
        color: #f0f0f0;
        border: 1px solid #555;
        border-radius: 4px;
        margin-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 3px;
        color: #f0f0f0;
    }
    QDockWidget {
        background-color: #2b2b2b;
        color: #f0f0f0;
        border: 1px solid #555;
    }
    QDockWidget::title {
        background-color: #3a3a3a;
        padding: 5px;
        text-align: center;
    }
    QMenuBar {
        background-color: #3a3a3a;
        color: #f0f0f0;
    }
    QMenuBar::item {
        padding: 5px 10px;
        background-color: transparent;
    }
    QMenuBar::item:selected {
        background-color: #007acc;
    }
    QMenu {
        background-color: #3a3a3a;
        color: #f0f0f0;
        border: 1px solid #555;
    }
    QMenu::item {
        padding: 5px 20px;
    }
    QMenu::item:selected {
        background-color: #007acc;
    }
    QToolBar {
        background-color: #3a3a3a;
        border: none;
        padding: 5px;
    }
    QToolButton {
        background-color: transparent;
        border: none;
        padding: 5px;
    }
    QToolButton:hover {
        background-color: #005f99;
    }
    QToolButton:pressed {
        background-color: #003f66;
    }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())