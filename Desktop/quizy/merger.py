import os
import re
from io import StringIO

# Importujemy z pdfminer.six
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
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


def extract_text_with_pdfminer(pdf_path):
    """
    Ekstrahuje tekst z PDF z lepszym zachowaniem układu za pomocą pdfminer.six.
    Dostosowane LAParams dla lepszej separacji linii.
    """
    output_string = StringIO()
    # Dostosowane LAParams - line_margin (domyślnie 0.5) i word_margin (domyślnie 0.1)
    # Zwiększenie line_margin może pomóc w oddzielaniu linii, które są "blisko siebie" pionowo,
    # ale powinny być traktowane jako osobne, np. różne odpowiedzi.
    # Użycie domyślnych na początek, jeśli nie działa, można eksperymentować.
    laparams = LAParams(line_margin=0.6, char_margin=2.0)  # Zwiększ marginesy
    with open(pdf_path, "rb") as in_file:
        extract_text_to_fp(
            in_file, output_string, laparams=laparams, output_type="text", codec="utf-8"
        )
    return output_string.getvalue()


def parse_pdf_for_questions(pdf_path):
    """
    Parsuje tekst z pojedynczego pliku PDF i wyodrębnia pytania,
    dostępne odpowiedzi i zidentyfikowane poprawne odpowiedzi,
    używając tekstu z pdfminer.six i regex.
    """
    questions = []
    full_text = extract_text_with_pdfminer(pdf_path)

    # Używamy unikalnych znaczników końca sekcji, jeśli tekst jest zbyt "zbity"
    # Jeśli nadal są problemy, możesz zmodyfikować pierwszy skrypt, aby dodawał
    # np. `###KONIEC_DOSTEPNYCH_ODPOWIEDZI###`

    # Regex do dopasowania całych bloków pytań. Używamy (?s) dla flagi DOTALL.
    # Wzorzec szuka "Pytanie:", potem dowolnego tekstu (nie zachłanne),
    # potem "Dostępne odpowiedzi:", dowolnego tekstu (nie zachłanne),
    # potem "Poprawna odpowiedź:", i dowolnego tekstu (nie zachłanne) do
    # kolejnego "Pytanie:" lub "--- PAGE \d+ ---" lub końca pliku.
    # Dodano opcjonalne znaczniki stron w regexie.
    question_pattern = re.compile(
        r"Pytanie:\s*(.*?)\s*Dostępne odpowiedzi:\s*(.*?)\s*Poprawna odpowiedź:\s*(.*?)(?=\s*Pytanie:|\s*--- PAGE \d+ ---|\Z)",
        re.DOTALL,
    )

    matches = question_pattern.finditer(full_text)

    for match in matches:
        question_text_raw = match.group(1).strip()
        all_answers_raw = match.group(2).strip()
        correct_answer_raw = match.group(3).strip()

        # Usuwamy wszelkie znaczniki stron, które mogły się wślizgnąć w tekst
        question_text_raw = re.sub(r"--- PAGE \d+ ---", "", question_text_raw).strip()
        all_answers_raw = re.sub(r"--- PAGE \d+ ---", "", all_answers_raw).strip()
        correct_answer_raw = re.sub(r"--- PAGE \d+ ---", "", correct_answer_raw).strip()

        # --- NOWA LOGIKA PARSOWANIA Dostępnych Odpowiedzi ---
        all_answers = []
        # Wzorzec dopasowujący pojedynczą odpowiedź: zaczyna się od '-', potem dowolny tekst,
        # aż do kolejnego '-' lub końca sekcji odpowiedzi.
        # Używamy (?s) wew. wyrażenia, aby kropka działała na wiele linii.
        # (?:-|\Z) to szukanie kolejnego minusa LUB końca stringa
        answer_option_pattern = re.compile(
            r"-\s*(.*?)(?=\s*-|\s*Poprawna odpowiedź:|\Z)", re.DOTALL
        )

        # Znajdujemy wszystkie dopasowania opcji w bloku 'Dostępne odpowiedzi'
        # Odpowiedzi mogą być złamane na wiele linii, więc używamy finditer na całym bloku all_answers_raw
        for ans_match in answer_option_pattern.finditer(all_answers_raw):
            ans_text = ans_match.group(1).strip()
            if ans_text:
                all_answers.append(ans_text)

        # --- NOWA LOGIKA PARSOWANIA Poprawnej Odpowiedzi ---
        correct_answers = []
        has_identified_correct_answer = False

        if "(nie udało się zidentyfikować lub brak)" not in correct_answer_raw:
            has_identified_correct_answer = True
            # Używamy tego samego wzorca dla poprawnych odpowiedzi
            for corr_ans_match in answer_option_pattern.finditer(correct_answer_raw):
                ans_text = corr_ans_match.group(1).strip()
                if ans_text:
                    correct_answers.append(ans_text)

            # Dodatkowa obsługa, jeśli poprawna odpowiedź nie ma formatu listy (-)
            if (
                not correct_answers
                and correct_answer_raw.strip()
                and not correct_answer_raw.strip().startswith("(")
            ):
                # Jeśli wciąż brak, a tekst jest, potraktuj całą zawartość jako jedną odpowiedź
                # o ile nie jest to komunikat o braku odpowiedzi
                correct_answers.append(correct_answer_raw.strip())

        # Upewnij się, że tekst pytania jest czysty
        question_text = question_text_raw.strip()

        questions.append(
            {
                "question_text": question_text,
                "all_answers": all_answers,
                "correct_answers": correct_answers,
                "has_identified_correct_answer": has_identified_correct_answer,
            }
        )
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
    input_pdf_directory = "wdrazanie_uslugi/result_pdf"  # Katalog z PDF-ami wygenerowanymi przez pierwszy skrypt
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

            # Jeśli pytanie ma zidentyfikowaną odpowiedź, dodaj je do słownika unikalnych
            if q_data["has_identified_correct_answer"]:
                if cleaned_question_text not in unique_questions_identified:
                    unique_questions_identified[cleaned_question_text] = q_data
            else:
                # Pytania bez zidentyfikowanej odpowiedzi trafiają do osobnej listy.
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
