from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtCore import Qt, QRect

import arithmetic as arith

class MachineView(QWidget):
    def __init__(self, emulator_state, parent=None):
        super().__init__(parent)
        self.es = emulator_state
        self.setMinimumSize(800, 600) # Adjust size for diagram
        self.previous_reg_values = {} # Initialize dictionary to store previous register values

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Define colors for the diagram
        background_color = QColor("#1a1a1a")
        component_fill_color = QColor("#2a2a2a")
        component_border_color = QColor("#007acc")
        text_color = QColor("#e0e0e0")
        value_color = QColor("#00ff00") # Green for dynamic values
        bus_color = QColor("#ff8c00") # Orange for buses
        highlight_color = QColor("#ffff00") # Yellow for highlighting

        # Fill background
        painter.fillRect(self.rect(), background_color)

        painter.setPen(QPen(component_border_color, 2))
        painter.setFont(QFont("Arial", 10))

        # --- CPU Block ---
        cpu_rect = QRect(self.width() // 2 - 150, 50, 300, 200)
        painter.fillRect(cpu_rect, component_fill_color)
        painter.drawRect(cpu_rect)
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        painter.drawText(cpu_rect.adjusted(0, 0, 0, -cpu_rect.height() + 30), Qt.AlignCenter, "CPU")

        # Internal CPU components (simplified)
        painter.setFont(QFont("Arial", 10))
        painter.setPen(QPen(component_border_color, 1))

        alu_rect = QRect(cpu_rect.x() + 20, cpu_rect.y() + 50, 120, 60)
        painter.fillRect(alu_rect, QColor("#3a3a3a"))
        painter.drawRect(alu_rect)
        painter.setPen(text_color)
        painter.drawText(alu_rect, Qt.AlignCenter, "ALU")

        control_unit_rect = QRect(cpu_rect.x() + 160, cpu_rect.y() + 50, 120, 60)
        painter.fillRect(control_unit_rect, QColor("#3a3a3a"))
        painter.drawRect(control_unit_rect)
        painter.setPen(text_color)
        painter.drawText(control_unit_rect, Qt.AlignCenter, "Control Unit")

        # --- General Purpose Registers (R0-R15) ---
        gpr_rect = QRect(50, cpu_rect.y(), 120, 280) # Increased height from 200 to 280
        painter.fillRect(gpr_rect, component_fill_color)
        painter.drawRect(gpr_rect)
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(gpr_rect.adjusted(0, 0, 0, -gpr_rect.height() + 20), Qt.AlignCenter, "GPRs")

        painter.setFont(QFont("Courier New", 9))
        reg_y_offset = gpr_rect.y() + 30
        reg_height = 15
        for i in range(16):
            reg_name = f"R{i}"
            value = self.es.regfile[i].get() if self.es and self.es.regfile and i < len(self.es.regfile) else 0x0000
            
            # Highlight if value changed
            if reg_name in self.previous_reg_values and self.previous_reg_values[reg_name] != value:
                painter.setPen(QPen(highlight_color, 1))
            else:
                painter.setPen(text_color)

            painter.drawText(gpr_rect.x() + 5, reg_y_offset + i * reg_height, f"{reg_name}: 0x{value:04X}")
            self.previous_reg_values[reg_name] = value # Update previous value for next repaint

        # --- Control Registers ---
        cr_rect = QRect(cpu_rect.x(), cpu_rect.bottom() + 30, cpu_rect.width(), 150)
        painter.fillRect(cr_rect, component_fill_color)
        painter.drawRect(cr_rect)
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(cr_rect.adjusted(0, 0, 0, -cr_rect.height() + 20), Qt.AlignCenter, "Control Registers")

        painter.setFont(QFont("Courier New", 9))
        cr_y_offset = cr_rect.y() + 30
        cr_x_offset = cr_rect.x() + 10
        cr_line_height = 15

        # PC
        pc_value = self.es.pc.get() if self.es and self.es.pc else 0x0000
        painter.setPen(value_color)
        painter.drawText(cr_x_offset, cr_y_offset, f"PC: 0x{pc_value:04X}")

        # IR
        ir_value = self.es.ir.get() if self.es and self.es.ir else 0x0000
        painter.drawText(cr_x_offset, cr_y_offset + cr_line_height, f"IR: 0x{ir_value:04X}")

        # Other control registers (simplified, can add more as needed)
        status_value = self.es.status_reg.get() if self.es and self.es.status_reg else 0x0000
        painter.drawText(cr_x_offset, cr_y_offset + 2 * cr_line_height, f"Status: 0x{status_value:04X}")

        # --- Memory Block ---
        mem_rect = QRect(self.width() - 150, cpu_rect.y(), 100, 200)
        painter.fillRect(mem_rect, component_fill_color)
        painter.drawRect(mem_rect)
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(mem_rect.adjusted(0, 0, 0, -mem_rect.height() + 20), Qt.AlignCenter, "Memory")

        painter.setFont(QFont("Courier New", 8))
        mem_y_offset = mem_rect.y() + 30
        mem_x_offset = mem_rect.x() + 5
        mem_line_height = 12
        for i in range(8): # Display first 8 memory locations
            addr = i
            value = self.es.ab.read_mem16(self.es, addr) if self.es and self.es.ab else 0x0000
            painter.setPen(value_color)
            painter.drawText(mem_x_offset, mem_y_offset + i * mem_line_height, f"0x{addr:04X}: 0x{value:04X}")

        # --- Buses (simplified lines) ---
        painter.setPen(QPen(bus_color, 2, Qt.DotLine)) # Dotted lines for buses

        # CPU to GPRs (Data/Control)
        painter.drawLine(cpu_rect.left(), cpu_rect.center().y(), gpr_rect.right(), gpr_rect.center().y())

        # CPU to Control Registers (Control)
        painter.drawLine(cpu_rect.center().x(), cpu_rect.bottom(), cr_rect.center().x(), cr_rect.top())

        # CPU to Memory (Address/Data/Control)
        painter.drawLine(cpu_rect.right(), cpu_rect.center().y(), mem_rect.left(), mem_rect.center().y())

        painter.end()

    def update_view(self):
        self.update() # Schedules a paintEvent call
