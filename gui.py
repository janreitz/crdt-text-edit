from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, QTimer

from PyQt5 import QtWidgets, uic
import sys
sys.path.insert(0, r"C:\Users\reitz\PersonalProjects\crdt")
import crdt
import crdt_test

class EditorUI(QtWidgets.QMainWindow):
    def __init__(self, window_title: str="Collaboration!"):
        super(EditorUI, self).__init__()
        uic.loadUi('editor.ui', self)
        self.setWindowTitle(window_title)
        self.online_indicator = QtWidgets.QCheckBox()
        self.online_indicator.setText("Online")
        self.online_indicator.setEnabled(False)
        self.status_bar.addWidget(self.online_indicator)
        self.file_path = None
        self.action_open.triggered.connect(self.slot_action_open)
        self.action_save.triggered.connect(self.slot_action_save)
        self.action_save_as.triggered.connect(self.slot_action_save_as)
        self.show()

    @pyqtSlot()
    def slot_action_open(self):
        self.file_path = QtWidgets.QFileDialog.getOpenFileName()
        with open(self.file_path[0], "r") as f:
            self.textEdit.setText(f.read())

    @pyqtSlot()
    def slot_action_save(self):
        if not self.file_path:
            self.file_path = QtWidgets.QFileDialog.getSaveFileName()[0]
        with open(self.file_path[0], "w") as f:
            f.write(self.textEdit.toPlainText())

    @pyqtSlot()
    def slot_action_save_as(self):
        self.file_path = QtWidgets.QFileDialog.getSaveFileName()[0]
        with open(self.file_path[0], "w") as f:
            f.write(self.textEdit.toPlainText())

class NetworkSim(QObject):
    """
    Helper class to enable signal slot connection to 
    slot_simulate_sync
    """
    signal_sync_finished = pyqtSignal()

    def __init__(self, interfaces: ['CRDTInterface']):
        QObject.__init__(self)
        self.interfaces = interfaces
        self.timer = QTimer()
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.slot_simulate_sync)
        for interface in interfaces:
            self.signal_sync_finished.connect(interface.slot_process_queue)
            interface.ui.action_sync.triggered.connect(self.slot_simulate_sync)
            interface.ui.action_continuous_sync.triggered.connect(
                self.slot_action_continuous_sync)

    @pyqtSlot()
    def slot_simulate_sync(self):
        self.simulate_sync()

    @pyqtSlot()
    def slot_action_continuous_sync(self):
        if self.timer.isActive(): 
            self.timer.stop()
            online = False
        else: 
            self.timer.start()
            online = True
        for interface in self.interfaces:
            interface.ui.online_indicator.setChecked(online)

    def simulate_sync(self):
        crdt_test.simulate_sync_nowait([interface.crdt for interface in self.interfaces])
        self.signal_sync_finished.emit()

class CRDTInterface(QObject):
    """
    Interface between UI and CRDT
    """
    def __init__(self, ui: EditorUI, crdt_: crdt.AbstractCRDT):
        QObject.__init__(self)
        self.ui = ui
        self.crdt = crdt_
        self.text = ""
        self.ui.textEdit.textChanged.connect(self.slot_text_changed)
        self.ignore_slot_text_changed = False
        
    @pyqtSlot()
    def slot_text_changed(self):
        """
        This is triggered after each change, i.e. the
        change can only affect one character.
        """
        if self.ignore_slot_text_changed: return
        changed_text = self.ui.textEdit.toPlainText()
        ops = rga_diff(self.text, changed_text)
        for op in ops:
            self.crdt.enqueue_op_nowait(op)
        self.crdt.process_queue_nowait()

        self.text = changed_text

        print(f"""Text: {self.text}
        CRDT Values: {self.text_from_rga(self.crdt)}""")

    @pyqtSlot()
    def slot_process_queue(self):
        if self.crdt.incoming_ops.empty(): return
        self.crdt.process_queue_nowait()
        self.text = self.text_from_rga(self.crdt)
        self.ignore_slot_text_changed = True
        self.ui.textEdit.setText(self.text)
        self.ignore_slot_text_changed = False

    @staticmethod
    def text_from_rga(rga: crdt.RGALinkedList) -> str:
        return ''.join([str(node) for node in rga])

def rga_diff(a_text, b_text) -> [crdt.Operation]:
    """
    Return RGA___Operation representing diff between b_text and a_text
    """
    ops = []
    i = 0 
    # One or more characters changed
    if len(a_text) == len(b_text):
        for a, b in zip(a_text, b_text):
            if a != b: ops.append(crdt.RGALocalUpdateOperation((i, b)))
            i = i + 1
        return ops
    # One or more characters were deleted
    if len(a_text) > len(b_text):
        # find the start of deletion
        for a, b in zip(a_text, b_text):
            if a != b: break
            i = i + 1
        # Append local deletes. These are processed sequentially.
        # The index must stay the same, because the part of the array 
        # after the delete shifts left.
        for _ in range(i, i + len(a_text) - len(b_text)):
            ops.append(crdt.RGALocalDeleteOperation(i))
        return ops
    # One or more character were inserted
    if len(a_text) < len(b_text):
        # find the start of insertion
        for a, b in zip(a_text, b_text):
            if a != b: break
            i = i + 1
        for ii in range(i, i + len(b_text) - len(a_text)):
            idx = ii - 1
            if idx < 0: idx = None
            ops.append(crdt.RGALocalInsertOperation((idx, b_text[ii])))
        return ops

if __name__=="__main__":    
    app = QtWidgets.QApplication([])

    input_1 = EditorUI("Site 1")
    text_1 = crdt.RGALinkedList(0, 3, 0, name="SITE 1")
    crdt_interface_1 = CRDTInterface(input_1, text_1)

    input_2 = EditorUI("Site 2")
    text_2 = crdt.RGALinkedList(0, 3, 1, name="SITE 2")
    crdt_interface_2 = CRDTInterface(input_2, text_2)    
    
    input_3 = EditorUI("Site 3")
    text_3 = crdt.RGALinkedList(0, 3, 2, name="SITE 3")
    crdt_interface_3 = CRDTInterface(input_3, text_3) 

    network_sim = NetworkSim([crdt_interface_1, crdt_interface_2, crdt_interface_3])

    app.exec_()