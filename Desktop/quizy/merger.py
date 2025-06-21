import os
import re

from pypdf import PdfReader, PdfWriter  # Używamy nowszej biblioteki pypdf
from reportlab.lib.colors import black, green, red
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

# --- WAŻNE: Konfiguracja czcionki dla polskich znaków ---
# Ponownie, aby polskie znaki były poprawnie wyświetlane w nowych PDF-ach,
# upewnij się, że pliki czcionek są dostępne w tym samym katalogu co skrypt.
FONT_NAME = "DejaVuSans"
FONT_FILE = "DejaVuSans.ttf"
FONT_BOLD_FILE = "DejaVuSans-Bold.ttf"

try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_FILE))
    if os.path.exists(FONT_BOLD_FILE):
        pdfmetrics.registerFont(TTFont(FONT_NAME + "-Bold", FONT_BOLD_FILE))
    else:
        print(f"Brak pliku {FONT_BOLD_FILE}. Pogrubienie będzie symulowane.")
    print(
        f"Czcionka '{FONT_NAME}' ({FONT_FILE}) zarejestrowana pomyślnie dla ReportLab."
    )
except Exception as e:
    print(
        f"!!! BŁĄD: Nie udało się zarejestrować czcionki '{FONT_NAME}' z pliku '{FONT_FILE}': {e}"
    )
    print(
        "Nowe pliki PDF zostaną wygenerowane z domyślnymi czcionkami (mogą brakować polskich znaków)."
    )
    print("Upewnij się, że pliki czcionek znajdują się w tym samym katalogu co skrypt.")
    FONT_NAME = "Helvetica"  # Fallback


def parse_pdf_for_questions(pdf_path):
    """
    Parsuje tekst z pojedynczego pliku PDF i wyodrębnia pytania,
    dostępne odpowiedzi i zidentyfikowane poprawne odpowiedzi.
    """
    questions = []
    try:
        reader = PdfReader(pdf_path)
        current_question = {}
        in_question_block = False
        in_answers_block = False
        in_correct_answer_block = False

        for page in reader.pages:
            text = page.extract_text()
            lines = text.split("\n")

            for line in lines:
                line = line.strip()

                if line.startswith("--- PAGE"):  # Ignoruj znaczniki stron ReportLab
                    continue

                if line.startswith("Pytanie:"):
                    if current_question:  # Zapisz poprzednie pytanie
                        questions.append(current_question)
                    current_question = {
                        "question_text": "",
                        "all_answers": [],
                        "correct_answers": [],
                        "has_identified_correct_answer": False,
                    }
                    in_question_block = True
                    in_answers_block = False
                    in_correct_answer_block = False
                    current_question["question_text"] = line.replace(
                        "Pytanie:", ""
                    ).strip()
                    continue

                if line.startswith("Dostępne odpowiedzi:"):
                    in_question_block = False
                    in_answers_block = True
                    in_correct_answer_block = False
                    continue

                if line.startswith("Poprawna odpowiedź:"):
                    in_question_block = False
                    in_answers_block = False
                    in_correct_answer_block = True
                    if "(nie udało się zidentyfikować lub brak)" not in line:
                        current_question["has_identified_correct_answer"] = True
                    else:
                        current_question["has_identified_correct_answer"] = (
                            False  # Wyraźnie oznacz
                        )

                    # Czasem odpowiedź jest od razu po "Poprawna odpowiedź:"
                    if (
                        "(nie udało się zidentyfikować lub brak)" not in line
                        and len(line.split(":", 1)) > 1
                    ):
                        remainder = line.split(":", 1)[1].strip()
                        if remainder and not remainder.startswith(
                            "("
                        ):  # Jeśli to nie jest komunikat o braku
                            # Usunięcie "- " na początku, jeśli tam jest
                            extracted_ans = remainder.lstrip("- ").strip()
                            if (
                                extracted_ans
                                and extracted_ans
                                not in current_question["correct_answers"]
                            ):
                                current_question["correct_answers"].append(
                                    extracted_ans
                                )
                    continue

                # Dodawanie treści do bieżących bloków
                if in_question_block and line:
                    current_question["question_text"] += " " + line
                elif in_answers_block and line.startswith("-"):
                    current_question["all_answers"].append(line.lstrip("- ").strip())
                elif in_correct_answer_block and line.startswith("-"):
                    # Ta linia powinna być przetwarzana tylko jeśli 'has_identified_correct_answer' jest True
                    # co oznacza, że poprzednia linia Poprawna odpowiedź: nie zawierała 'nie udało się zidentyfikować'
                    if current_question["has_identified_correct_answer"]:
                        current_question["correct_answers"].append(
                            line.lstrip("- ").strip()
                        )

        if current_question:  # Dodaj ostatnie pytanie
            questions.append(current_question)

    except Exception as e:
        print(f"Błąd podczas parsowania pliku PDF {pdf_path}: {e}")

    # Po zakończeniu parsowania każdej strony, oczyść tekst pytań i odpowiedzi
    for q in questions:
        q["question_text"] = q["question_text"].strip()
        q["all_answers"] = [ans.strip() for ans in q["all_answers"]]
        q["correct_answers"] = [ans.strip() for ans in q["correct_answers"]]

    return questions


def clean_text_for_deduplication(text):
    """
    Czyści tekst pytania do celów deduplikacji:
    usuwa znaki interpunkcyjne, zamienia na małe litery, usuwa białe znaki.
    """
    text = re.sub(r"[^\w\s]", "", text)  # Usuń znaki interpunkcyjne
    text = text.lower()  # Małe litery
    text = re.sub(r"\s+", " ", text).strip()  # Znormalizuj białe znaki
    return text


def generate_merged_pdf(output_pdf_path, questions_list):
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
        if FONT_NAME != "Helvetica" and os.path.exists(FONT_BOLD_FILE)
        else "Helvetica-Bold"
    )
    question_style.fontSize = 12
    question_style.leading = 14
    question_style.alignment = TA_LEFT
    question_style.spaceAfter = 6
    question_style.textColor = black

    answer_style = styles["Normal"]
    answer_style.fontName = FONT_NAME
    answer_style.fontSize = 10
    answer_style.leading = 12
    answer_style.leftIndent = 20
    answer_style.spaceAfter = 3
    answer_style.textColor = black

    correct_answer_style = styles["Normal"]
    correct_answer_style.fontName = FONT_NAME
    correct_answer_style.fontSize = 10
    correct_answer_style.leading = 12
    correct_answer_style.leftIndent = 20
    correct_answer_style.textColor = green
    correct_answer_style.spaceAfter = 3

    no_correct_answer_style = styles["Normal"]
    no_correct_answer_style.fontName = FONT_NAME
    no_correct_answer_style.fontSize = 10
    no_correct_answer_style.leading = 12
    no_correct_answer_style.leftIndent = 20
    no_correct_answer_style.textColor = red  # Zaznacz na czerwono, że brak odpowiedzi
    no_correct_answer_style.spaceAfter = 3

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
                # W tym generowaniu, kolorujemy tylko poprawną odpowiedź, jeśli jest znana.
                # W pliku "z identyfikacją" będzie zielona, w "bez identyfikacji" czarna
                # Chyba że chcemy zaznaczyć na czerwono, że nie ma poprawnej odpowiedzi.
                if (
                    q_data["has_identified_correct_answer"]
                    and ans in q_data["correct_answers"]
                ):
                    story.append(Paragraph(f"- {ans}", correct_answer_style))
                else:
                    story.append(Paragraph(f"- {ans}", answer_style))
            story.append(Spacer(1, 6))

        if q_data["has_identified_correct_answer"]:
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
    # --- Konfiguracja katalogów i nazw plików wyjściowych ---
    input_pdf_directory = (
        "result_pdf"  # Katalog z PDF-ami wygenerowanymi przez pierwszy skrypt
    )
    output_pdf_identified = "Merged_Quiz_Pytania_Z_Odpowiedziami.pdf"
    output_pdf_unidentified = "Merged_Quiz_Pytania_Bez_Odpowiedzi.pdf"
    # --- Konfiguracja End ---

    all_parsed_questions = []

    if not os.path.exists(input_pdf_directory):
        print(f"Błąd: Katalog '{input_pdf_directory}' nie istnieje.")
        print("Utwórz go i umieść w nim pliki PDF wygenerowane przez pierwszy skrypt.")
    else:
        for filename in os.listdir(input_pdf_directory):
            if filename.endswith(".pdf"):
                file_path = os.path.join(input_pdf_directory, filename)
                print(f"Parsuję PDF: {filename}")
                questions_from_pdf = parse_pdf_for_questions(file_path)
                all_parsed_questions.extend(questions_from_pdf)

        if not all_parsed_questions:
            print("Nie znaleziono żadnych pytań do przetworzenia w plikach PDF.")
            exit()

        # Deduplikacja pytań i segregacja
        unique_questions_identified = (
            {}
        )  # Klucz: wyczyszczony tekst pytania, Wartość: pełne dane pytania
        unidentified_questions = []

        for q_data in all_parsed_questions:
            cleaned_question_text = clean_text_for_deduplication(
                q_data["question_text"]
            )

            if q_data["has_identified_correct_answer"]:
                # Jeśli pytanie ma zidentyfikowaną odpowiedź, dodaj je do słownika unikalnych
                # lub zaktualizuj, jeśli już istnieje (ale powinno być unikalne po czyszczeniu)
                if cleaned_question_text not in unique_questions_identified:
                    unique_questions_identified[cleaned_question_text] = q_data
            else:
                # Pytania bez zidentyfikowanej odpowiedzi trafiają do osobnej listy
                unidentified_questions.append(q_data)

        # Konwersja słownika na listę do generowania PDF
        final_identified_questions = list(unique_questions_identified.values())

        print(
            f"Zidentyfikowano unikalnych pytań z odpowiedziami: {len(final_identified_questions)}"
        )
        print(f"Zidentyfikowano pytań bez odpowiedzi: {len(unidentified_questions)}")

        # Generowanie PDF-ów
        if final_identified_questions:
            generate_merged_pdf(output_pdf_identified, final_identified_questions)
        else:
            print(
                f"Brak pytań z zidentyfikowanymi odpowiedziami do wygenerowania '{output_pdf_identified}'."
            )

        if unidentified_questions:
            generate_merged_pdf(output_pdf_unidentified, unidentified_questions)
        else:
            print(
                f"Brak pytań bez zidentyfikowanych odpowiedzi do wygenerowania '{output_pdf_unidentified}'."
            )
