import os
from os.path import isfile
from os  import remove
import re

# Функция, которая создает заметки
def build_note(note_text, note_name):
    try:
        with open(f'{note_name}.txt', 'a', encoding="utf-8") as f:
            f.write(note_text + '\n')
        print(f'Заметка {note_name} создана.')
    except Exception as err:
        print(str(err))

# Функция, которая открывает\создает заметки
def create_note():
    try:
        note_name = input('Введите название заметки:')
        forbidden_symbols = "\\|/*<>?:"  #Набор запрещенных символов windows
        pattern = "[{0}]".format(forbidden_symbols)
        if re.search(pattern, note_name):
            print("Вы ввели недопустимые символы. Переименуйте заметку")
        else:
            print("Заметка создана")
            note_text = input('Введите содержимое заметки:')
            build_note(note_text, note_name)
    except:
        print("Что-то пошло не так. Попробуйте еще раз")\

# Функция, которая читает заметку
def read_note():
    try:
        note_name = input('Введите название заметки')
        if isfile(note_name):
            with open(f'{note_name}.txt', 'r', encoding="utf-8") as f:
                lines = f.read()
            print("Текст заметки: ", lines)
        else:
            print("Заметка не найдена")
    except:
        print("Что-то пошло не так. Попробуйте еще раз")

def edit_note():
    note_name = input('Введите название заметки')
    if isfile(note_name):
        with open(f'{note_name}.txt', 'a', encoding="utf-8") as f:
            f.write(input('Напишите новый текст'))
    else:
        print("Заметка не найдена")

def delete_note():
    note_name = input('Введите название заметки')
    if isfile(note_name):
        remove(note_name)
        print('Заметка успешно удалена')
    else:
        print("Заметка не найдена")

def main():
    while True:
        print('''
        Выберите одно из этих действий\n
        1: Создать новую заметку\n
        2: Прочитать содержимое заметки\n
        3: Изменить содержимое заметки\n
        4: Удалить заметку\n
        5: Упорядочить список заметок\n
        6: Выйти из программы
        ''')
        choice = input('Выберите, что бы вы хотели сделать')
        if choice == '1':
            create_note()
        if choice == '2':
            read_note()
        if choice == '3':
            edit_note()
        if choice == '4':
            delete_note()
        if choice == '5':
            display_sorted_notes()
        if choice == '6':
            break
        else:
            print('Вы ввели некоректное число')

def get_char_count(file_path):
    try:
        with open(file_path, 'r', encoding="utf-8") as f:
            return len(f.read())
    except:
        return 0

def display_note():
    notes = [note for note in os.listdir() if note.endswith('.txt')]
    files_ascending = list(sorted(notes, key=get_char_count))
    print(files_ascending)

def display_sorted_notes():
    notes = [note for note in os.listdir() if note.endswith('.txt')]
    files_descending = list(sorted(notes, key=get_char_count))
    print(files_descending)

main()