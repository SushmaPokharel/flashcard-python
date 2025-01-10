import sys
import sqlite3
import random
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QDialog, QFormLayout, QLineEdit,
    QMenu
)
from PyQt5.QtCore import Qt


class FlashcardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flashcards for Study")
        self.setGeometry(100, 100, 600, 400)

        self.db = sqlite3.connect('flashcards.db')
        self.create_tables()
        self.load_data()

        self.score = 0
        self.total = 0

        self.init_ui()

    def create_tables(self):
        cursor = self.db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            )
        ''')
        self.db.commit()

    def load_data(self):
        self.subjects = {}
        cursor = self.db.cursor()

        cursor.execute("SELECT * FROM subjects")
        subjects_data = cursor.fetchall()
        for subject in subjects_data:
            self.subjects[subject[1]] = []

        cursor.execute("SELECT * FROM flashcards")
        flashcards_data = cursor.fetchall()
        for flashcard in flashcards_data:
            subject_name = cursor.execute(
                "SELECT name FROM subjects WHERE id = ?", (flashcard[1],)
            ).fetchone()[0]
            self.subjects[subject_name].append((flashcard[0], flashcard[2], flashcard[3]))

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        self.info_label = QLabel("Welcome to Flashcards App", self)
        self.info_label.setAlignment(Qt.AlignCenter)

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels(['Subjects'])
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)

        self.populate_tree()

        self.score_label = QLabel(f"Score: {self.score}/{self.total}", self)

        self.add_button = QPushButton("Add Flashcard", self)
        self.add_button.clicked.connect(self.add_flashcard)

        self.review_button = QPushButton("Review Flashcards", self)
        self.review_button.clicked.connect(self.review_flashcard)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.review_button)

        layout.addWidget(self.info_label)
        layout.addWidget(self.tree)
        layout.addWidget(self.score_label)
        layout.addLayout(button_layout)

        central_widget.setLayout(layout)

        self.tree.itemClicked.connect(self.display_flashcard)

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

    def populate_tree(self):
        self.tree.clear()
        root = QTreeWidgetItem(["Root"])
        self.tree.addTopLevelItem(root)

        for subject in self.subjects:
            subject_item = QTreeWidgetItem([subject])
            root.addChild(subject_item)
            for flashcard_id, question, _ in self.subjects[subject]:
                flashcard_item = QTreeWidgetItem([question])
                flashcard_item.setData(0, Qt.UserRole, (subject, flashcard_id))
                subject_item.addChild(flashcard_item)

    def add_flashcard(self):
        add_card_dialog = AddFlashcardDialog(self)
        if add_card_dialog.exec_():
            subject, question, answer = add_card_dialog.get_flashcard()

            cursor = self.db.cursor()
            cursor.execute("INSERT OR IGNORE INTO subjects (name) VALUES (?)", (subject,))
            cursor.execute("""
                INSERT INTO flashcards (subject_id, question, answer)
                VALUES (
                    (SELECT id FROM subjects WHERE name = ?),
                    ?, ?
                )
            """, (subject, question, answer))
            self.db.commit()

            if subject not in self.subjects:
                self.subjects[subject] = []
            flashcard_id = cursor.lastrowid
            self.subjects[subject].append((flashcard_id, question, answer))

            self.populate_tree()

    def review_flashcard(self):
        selected_item = self.tree.selectedItems()
        if not selected_item:
            return

        subject_name = selected_item[0].text(0)
        if subject_name in self.subjects and self.subjects[subject_name]:
            flashcard = random.choice(self.subjects[subject_name])
            _, question, answer = flashcard

            review_dialog = ReviewFlashcardDialog(self, question, answer)
            if review_dialog.exec_():
                user_answer = review_dialog.get_answer()

                if user_answer.lower() == answer.lower():
                    self.score += 1

                self.total += 1
                self.update_score_label()

    def update_score_label(self):
        self.score_label.setText(f"Score: {self.score}/{self.total}")

    def display_flashcard(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data:
            subject, flashcard_id = data
            for subject_name, flashcards in self.subjects.items():
                for fid, question, answer in flashcards:
                    if fid == flashcard_id:
                        self.score_label.setText(f"{question}\nAnswer: {answer}")

    def show_context_menu(self, point):
        item = self.tree.itemAt(point)
        if item:
            menu = QMenu(self)
            delete_action = menu.addAction("Delete Flashcard")
            delete_action.triggered.connect(lambda: self.delete_flashcard(item))
            menu.exec_(self.tree.mapToGlobal(point))

    def delete_flashcard(self, item):
        data = item.data(0, Qt.UserRole)
        if data:
            subject, flashcard_id = data

            cursor = self.db.cursor()
            cursor.execute("DELETE FROM flashcards WHERE id = ?", (flashcard_id,))
            self.db.commit()

            if subject in self.subjects:
                self.subjects[subject] = [
                    flashcard for flashcard in self.subjects[subject] 
                    if flashcard[0] != flashcard_id
                ]

                if not self.subjects[subject]:
                    del self.subjects[subject]
                    cursor.execute("DELETE FROM subjects WHERE name = ?", (subject,))
                    self.db.commit()

            parent_item = item.parent()
            if parent_item:
                parent_item.removeChild(item)
                if parent_item.childCount() == 0:
                    root = self.tree.topLevelItem(0)
                    root.removeChild(parent_item)


class AddFlashcardDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Add Flashcard")

        self.subject_input = QLineEdit(self)
        self.question_input = QLineEdit(self)
        self.answer_input = QLineEdit(self)

        layout = QFormLayout(self)
        layout.addRow("Subject:", self.subject_input)
        layout.addRow("Question:", self.question_input)
        layout.addRow("Answer:", self.answer_input)

        self.save_button = QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_flashcard)

        layout.addRow(self.save_button)
        self.setLayout(layout)

    def save_flashcard(self):
        self.accept()

    def get_flashcard(self):
        subject = self.subject_input.text().strip()
        question = self.question_input.text().strip()
        answer = self.answer_input.text().strip()
        return subject, question, answer


class ReviewFlashcardDialog(QDialog):
    def __init__(self, parent, question, answer):
        super().__init__(parent)
        self.setWindowTitle("Review Flashcard")
        self.question = question
        self.answer = answer
        self.user_answer_input = QLineEdit(self)

        layout = QFormLayout(self)
        layout.addRow("Question:", QLabel(self.question))
        layout.addRow("Your Answer:", self.user_answer_input)

        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submit_answer)

        layout.addRow(self.submit_button)
        self.setLayout(layout)

    def submit_answer(self):
        self.accept()

    def get_answer(self):
        return self.user_answer_input.text().strip()


def main():
    app = QApplication(sys.argv)
    window = FlashcardApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
