import json
import os
import re

from reportlab.lib.colors import black, green, red
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

# --- WAŻNE: Konfiguracja czcionki dla polskich znaków ---
FONT_NAME = "DejaVuSans"
FONT_FILE = "DejaVuSans.ttf"
FONT_BOLD_FILE = "DejaVuSans-Bold.ttf"

try:
    # Weryfikacja, czy pliki czcionek istnieją
    if not os.path.exists(FONT_FILE):
        raise FileNotFoundError(
            f"Brak pliku czcionki: {FONT_FILE}. Upewnij się, że znajduje się w tym samym katalogu co skrypt."
        )
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_FILE))

    if os.path.exists(FONT_BOLD_FILE):
        pdfmetrics.registerFont(TTFont(FONT_NAME + "-Bold", FONT_BOLD_FILE))
        font_bold_registered = True
    else:
        print(
            f"Brak pliku {FONT_BOLD_FILE}. Pogrubienie będzie symulowane przez ReportLab."
        )
        font_bold_registered = False

    print(
        f"Czcionka '{FONT_NAME}' ({FONT_FILE}) zarejestrowana pomyślnie dla ReportLab."
    )
except Exception as e:
    print(f"!!! BŁĄD: Nie udało się zarejestrować czcionki '{FONT_NAME}': {e}")
    print(
        "Nowe pliki PDF zostaną wygenerowane z domyślnymi czcionkami (mogą brakować polskich znaków)."
    )
    print(
        "Upewnij się, że pliki czcionek (.ttf) znajdują się w tym samym katalogu co skrypt."
    )
    FONT_NAME = "Helvetica"  # Fallback
    font_bold_registered = False  # Ustaw na False, nawet jeśli Helvetica-Bold jest dostępna, aby logika stylów była spójna


def clean_text_for_deduplication(text):
    """
    Czyści tekst pytania do celów deduplikacji:
    usuwa znaki interpunkcyjne, zamienia na małe litery, usuwa białe znaki.
    """
    if not isinstance(text, str):
        return ""
    text = re.sub(
        r"[^\w\sąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", "", text
    )  # Usuń znaki interpunkcyjne, zachowaj polskie znaki
    text = text.lower()  # Małe litery
    text = re.sub(r"\s+", " ", text).strip()  # Znormalizuj białe znaki
    return text


def generate_pdf_from_questions(
    output_pdf_path, questions_list, title="Pytania i Odpowiedzi"
):
    """
    Generuje pojedynczy plik PDF z listą pytań.
    """
    doc = SimpleDocTemplate(output_pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Zdefiniuj style z uwzględnieniem zarejestrowanej czcionki
    question_style = styles["Normal"]
    question_style.fontName = (
        FONT_NAME + "-Bold"
        if FONT_NAME != "Helvetica" and font_bold_registered
        else "Helvetica-Bold"
    )
    question_style.fontSize = 12
    question_style.leading = 14
    question_style.alignment = TA_LEFT
    question_style.spaceAfter = 6
    question_style.textColor = black
    question_style.allowBreakWords = True  # Pozwól na łamanie słów
    question_style.splitLongWords = True  # Rozdzielaj długie słowa
    question_style.wordWrap = "CJK"  # Ułatwia łamanie wierszy

    answer_style = styles["Normal"]
    answer_style.fontName = FONT_NAME
    answer_style.fontSize = 10
    answer_style.leading = 12
    answer_style.leftIndent = 20
    answer_style.spaceAfter = 3
    answer_style.textColor = black
    answer_style.allowBreakWords = True
    answer_style.splitLongWords = True
    answer_style.wordWrap = "CJK"

    correct_answer_style = styles["Normal"]
    correct_answer_style.fontName = FONT_NAME
    correct_answer_style.fontSize = 10
    correct_answer_style.leading = 12
    correct_answer_style.leftIndent = 20
    correct_answer_style.textColor = green
    correct_answer_style.spaceAfter = 3
    correct_answer_style.allowBreakWords = True
    correct_answer_style.splitLongWords = True
    correct_answer_style.wordWrap = "CJK"

    no_correct_answer_style = styles["Normal"]
    no_correct_answer_style.fontName = FONT_NAME
    no_correct_answer_style.fontSize = 10
    no_correct_answer_style.leading = 12
    no_correct_answer_style.leftIndent = 20
    no_correct_answer_style.textColor = red  # Zaznacz na czerwono, że brak odpowiedzi
    no_correct_answer_style.spaceAfter = 3
    no_correct_answer_style.allowBreakWords = True
    no_correct_answer_style.splitLongWords = True
    no_correct_answer_style.wordWrap = "CJK"

    # Dodaj tytuł na pierwszej stronie
    story.append(Paragraph(f'<h1 align="center">{title}</h1>', styles["h1"]))
    story.append(Spacer(1, 24))

    for i, q_data in enumerate(questions_list):
        if not q_data["question_text"].strip():
            continue

        if i > 0:  # Dodaj podział strony, ale nie przed pierwszym pytaniem
            story.append(PageBreak())

        story.append(Paragraph(f"<b>Pytanie {i+1}:</b>", question_style))
        story.append(Paragraph(q_data["question_text"], question_style))
        story.append(Spacer(1, 6))

        if q_data["all_answers"]:
            story.append(Paragraph("<b>Dostępne odpowiedzi:</b>", answer_style))
            for ans in q_data["all_answers"]:
                # Sprawdź, czy dana odpowiedź jest poprawna i pokoloruj ją
                if ans in q_data["correct_answers"]:  # Porównanie z danymi z JSON
                    story.append(Paragraph(f"- {ans}", correct_answer_style))
                else:
                    story.append(Paragraph(f"- {ans}", answer_style))
            story.append(Spacer(1, 6))

        if q_data[
            "correct_answers"
        ]:  # Sprawdź, czy są jakieś poprawne odpowiedzi w danych z JSON
            story.append(Paragraph("<b>Poprawna odpowiedź:</b>", correct_answer_style))
            for corr_ans in q_data["correct_answers"]:
                story.append(Paragraph(f"- {corr_ans}", correct_answer_style))
        else:
            story.append(
                Paragraph(
                    "<b>Poprawna odpowiedź:</b> (nie udało się zidentyfikować lub brak)",
                    no_correct_answer_style,
                )
            )

        story.append(Spacer(1, 12))

    try:
        doc.build(story)
        print(f"Pomyślnie wygenerowano plik PDF: {output_pdf_path}")
    except Exception as e:
        print(f"Wystąpił błąd podczas generowania pliku PDF {output_pdf_path}: {e}")


if __name__ == "__main__":
    # --- Konfiguracja katalogów i nazw plików wejściowych/wyjściowych ---
    input_json_file = "modelowanie_procesow_biznesowych/all_quiz_questions.json"  # Plik JSON wygenerowany przez html_to_json.py
    output_pdf_identified = "Merged_Quiz_Pytania_Z_Odpowiedziami.pdf"
    output_pdf_unidentified = "Merged_Quiz_Pytania_Bez_Odpowiedziami.pdf"  # Pytania bez zidentyfikowanych odpowiedzi
    # --- Konfiguracja End ---

    all_parsed_questions = []

    if not os.path.exists(input_json_file):
        print(f"Błąd: Plik '{input_json_file}' nie istnieje.")
        print("Najpierw uruchom 'html_to_json.py' aby wygenerować plik JSON.")
        exit()
    else:
        try:
            with open(input_json_file, "r", encoding="utf-8") as f:
                all_parsed_questions = json.load(f)
            print(f"Wczytano {len(all_parsed_questions)} pytań z pliku JSON.")
        except json.JSONDecodeError as e:
            print(f"Błąd dekodowania JSON z pliku {input_json_file}: {e}")
            print("Sprawdź, czy plik JSON jest poprawnie sformatowany.")
            exit()
        except Exception as e:
            print(f"Błąd podczas wczytywania pliku JSON {input_json_file}: {e}")
            exit()

        if not all_parsed_questions:
            print("Plik JSON nie zawiera żadnych pytań do przetworzenia.")
            exit()

        # Deduplikacja pytań i segregacja
        # Klucz: wyczyszczony tekst pytania
        # Wartość: pełne dane pytania
        unique_questions_map = {}

        for q_data in all_parsed_questions:
            cleaned_question_text = clean_text_for_deduplication(
                q_data.get("question_text", "")
            )

            # Pomiń puste pytania
            if not cleaned_question_text:
                continue

            # Sprawdzamy, czy pytanie ma zidentyfikowaną poprawną odpowiedź
            # Bierzemy pod uwagę, że correct_answers to lista
            has_identified_correct_answer = bool(
                q_data.get("correct_answers") and len(q_data["correct_answers"]) > 0
            )

            # Jeśli pytanie nie ma jeszcze w mapie, dodaj je
            if cleaned_question_text not in unique_questions_map:
                unique_questions_map[cleaned_question_text] = {
                    "data": q_data,
                    "has_correct_answer_flag": has_identified_correct_answer,  # Flaga do śledzenia
                }
            else:
                # Jeśli pytanie już jest, ale nowa wersja ma poprawną odpowiedź, a stara nie miała
                # LUB nowa wersja ma więcej poprawnych odpowiedzi (dla wielokrotnego wyboru, np.)
                current_entry = unique_questions_map[cleaned_question_text]

                # Warunek priorytetu: jeśli nowa wersja ma odpowiedź, a obecna nie, lub nowa ma więcej odpowiedzi
                if (
                    has_identified_correct_answer
                    and not current_entry["has_correct_answer_flag"]
                ):
                    unique_questions_map[cleaned_question_text] = {
                        "data": q_data,
                        "has_correct_answer_flag": has_identified_correct_answer,
                    }
                # Opcjonalnie: jeśli obie mają odpowiedzi, ale nowa ma więcej opcji odpowiedzi (może być bardziej kompletna)
                # elif has_identified_correct_answer and current_entry['has_correct_answer_flag'] and \
                #      len(q_data['correct_answers']) > len(current_entry['data']['correct_answers']):
                #      unique_questions_map[cleaned_question_text] = {
                #         'data': q_data,
                #         'has_correct_answer_flag': has_identified_correct_answer
                #     }

        # Segregacja na dwie listy: z odpowiedziami i bez (po deduplikacji)
        final_identified_questions = []
        final_unidentified_questions = []

        for cleaned_text, entry in unique_questions_map.items():
            if entry["has_correct_answer_flag"]:
                final_identified_questions.append(entry["data"])
            else:
                final_unidentified_questions.append(entry["data"])

        # Sortowanie dla spójności (opcjonalne, ale pomocne)
        final_identified_questions.sort(
            key=lambda x: clean_text_for_deduplication(x.get("question_text", ""))
        )
        final_unidentified_questions.sort(
            key=lambda x: clean_text_for_deduplication(x.get("question_text", ""))
        )

        print(
            f"Zidentyfikowano unikalnych pytań z odpowiedziami: {len(final_identified_questions)}"
        )
        print(
            f"Zidentyfikowano unikalnych pytań bez odpowiedzi: {len(final_unidentified_questions)}"
        )

        # Generowanie PDF-ów
        if final_identified_questions:
            generate_pdf_from_questions(
                output_pdf_identified,
                final_identified_questions,
                "Quiz: Pytania z Poprawnymi Odpowiedziami",
            )
        else:
            print(
                f"Brak pytań z zidentyfikowanymi odpowiedziami do wygenerowania '{output_pdf_identified}'."
            )

        if final_unidentified_questions:
            generate_pdf_from_questions(
                output_pdf_unidentified,
                final_unidentified_questions,
                "Quiz: Pytania Bez Zidentyfikowanych Odpowiedzi",
            )
        else:
            print(
                f"Brak pytań bez zidentyfikowanych odpowiedzi do wygenerowania '{output_pdf_unidentified}'."
            )
