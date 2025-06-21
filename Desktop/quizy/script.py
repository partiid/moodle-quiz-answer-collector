import os

from bs4 import BeautifulSoup
from reportlab.lib.colors import black, green, red
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

# --- WAŻNE: Konfiguracja czcionki dla polskich znaków ---
# Aby polskie znaki (ą, ć, ę, ł, ń, ó, ś, ź, ż) były poprawnie wyświetlane w PDF,
# MUSISZ UŻYĆ CZCIONKI TrueType (TTF), która je zawiera i ZAREJESTROWAĆ JĄ W ReportLab.
#
# Poniżej przykład z czcionką "DejaVuSans".
# KROK 1: POBIERZ PLIK CZCIONKI:
#   Przejdź na stronę: https://dejavu-fonts.github.io/
#   Pobierz pakiet DejaVu Fonts (zazwyczaj jako .zip).
#   Rozpakuj archiwum i znajdź plik "DejaVuSans.ttf" (lub "DejaVuSans-Bold.ttf" dla pogrubionej wersji)
#   w folderze "ttf".
#
# KROK 2: UMIEŚĆ PLIK CZCIONKI:
#   Skopiuj "DejaVuSans.ttf" (i ewentualnie "DejaVuSans-Bold.ttf")
#   DO TEGO SAMEGO KATALOGU, W KTÓRYM ZNAJDUJE SIĘ TEN SKRYPT PYTHONA.
#
# KROK 3: UPEWNIJ SIĘ, ŻE NAZWA PLIKU CZCIONKI JEST POPRAWNA PONIŻEJ.

# Domyślna nazwa czcionki, której będziemy używać w PDF
FONT_NAME = "DejaVuSans"
FONT_FILE = "DejaVuSans.ttf"
FONT_BOLD_FILE = "DejaVuSans-Bold.ttf"  # Opcjonalnie dla pogrubienia

try:
    # Rejestrujemy czcionkę regularną
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_FILE))
    # Rejestrujemy pogrubioną wersję (jeśli istnieje, inaczej ReportLab spróbuje pogrubić domyślnie)
    if os.path.exists(FONT_BOLD_FILE):
        pdfmetrics.registerFont(TTFont(FONT_NAME + "-Bold", FONT_BOLD_FILE))
    else:
        print(f"Brak pliku {FONT_BOLD_FILE}. Pogrubienie będzie symulowane.")

    print(f"Czcionka '{FONT_NAME}' ({FONT_FILE}) zarejestrowana pomyślnie.")
except Exception as e:
    print(
        f"!!! BŁĄD: Nie udało się zarejestrować czcionki '{FONT_NAME}' z pliku '{FONT_FILE}': {e}"
    )
    print(
        "PDF zostanie wygenerowany z domyślnymi czcionkami ReportLab (mogą brakować polskich znaków)."
    )
    print("Upewnij się, że plik czcionki znajduje się w tym samym katalogu co skrypt.")
    FONT_NAME = "Helvetica"  # Fallback na domyślną czcionkę ReportLab


def extract_answer_text(option_container):
    """
    Wyodrębnia czysty tekst odpowiedzi z kontenera opcji,
    usuwając numerację (a., b., ...) i zbędne frazy.
    """
    answer_label_div = option_container.find("div", class_="d-flex")
    if not answer_label_div:
        return ""

    # Klonujemy div, aby nie modyfikować oryginalnego obiektu BeautifulSoup
    # (może być używany do innych sprawdzeń)
    cloned_answer_label_div = BeautifulSoup(str(answer_label_div), "html.parser")

    # Usuń span z numerem odpowiedzi (a., b., ...)
    answernumber_span = cloned_answer_label_div.find("span", class_="answernumber")
    if answernumber_span:
        answernumber_span.decompose()

    # Wyciągnij tekst, łącząc go spacjami
    option_text = cloned_answer_label_div.get_text(separator=" ", strip=True)

    # Usuń frazy, które Moodle dodaje do tekstu odpowiedzi w widoku przeglądu
    option_text = (
        option_text.replace("Twoja odpowiedź jest poprawna.", "")
        .replace("Wybrano.", "")
        .strip()
    )

    return option_text


def parse_moodle_quiz_review(html_file_path):
    """
    Parsuje pojedynczy plik HTML z przeglądu quizu Moodle
    i wyodrębnia pytania wraz z odpowiedziami.
    """
    questions_data = []
    try:
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Błąd: Plik nie znaleziony pod ścieżką: {html_file_path}")
        return []
    except Exception as e:
        print(f"Wystąpił błąd podczas odczytu pliku {html_file_path}: {e}")
        return []

    soup = BeautifulSoup(html_content, "html.parser")

    question_blocks = soup.find_all("div", class_="que")

    if not question_blocks:
        print(f"Brak bloków pytań (div class='que') w pliku: {html_file_path}")
        return []

    for q_block in question_blocks:
        question_text = ""
        all_answers = []
        correct_answers = []  # Lista, bo może być wiele poprawnych odpowiedzi

        # 1. Znajdź treść pytania
        qtext_div = q_block.find("div", class_="qtext")
        if qtext_div:
            for flag_div in qtext_div.find_all("div", class_="questionflag"):
                flag_div.decompose()
            question_text = qtext_div.get_text(separator=" ", strip=True)

        # 2. Znajdź blok odpowiedzi i opcje
        answer_div = q_block.find("div", class_="answer")
        if answer_div:
            # Kontenery opcji to div z klasami 'r0' lub 'r1'
            option_containers = answer_div.find_all(["div"], class_=["r0", "r1"])

            for option_container in option_containers:
                option_text = extract_answer_text(option_container)

                if option_text and option_text not in all_answers:
                    all_answers.append(option_text)

                # 3. Sprawdź, czy odpowiedź jest poprawna - używamy najbardziej niezawodnych wskaźników
                is_this_option_correct = False

                # Poprawna odpowiedź ma klasę 'correct' LUB ikonę 'fa-check'
                if "correct" in option_container.get("class", []):
                    is_this_option_correct = True

                if option_container.find(
                    "i", class_="fa-check"
                ):  # Ikona zielonego checkmarka
                    is_this_option_correct = True

                # Czasem jest feedback "Twoja odpowiedź jest poprawna." wewnątrz samej opcji
                feedback_div_inside_option = option_container.find(
                    "div", class_="feedback"
                )
                if (
                    feedback_div_inside_option
                    and "Twoja odpowiedź jest poprawna."
                    in feedback_div_inside_option.get_text()
                ):
                    is_this_option_correct = True

                if is_this_option_correct and option_text not in correct_answers:
                    correct_answers.append(option_text)

        # 4. Dodatkowe sprawdzenie dla poprawnych odpowiedzi w bloku 'outcome'
        # To jest ważne, gdy np. użytkownik odpowiedział błędnie, a Moodle na dole pytania
        # wskazuje "Poprawna odpowiedź to: [treść]".
        outcome_div = q_block.find("div", class_="outcome")
        if outcome_div:
            # Szukamy span z klasą 'correct' lub ogólnego tekstu feedbacku
            correct_feedback_span = outcome_div.find("span", class_="correct")
            if correct_feedback_span:
                feedback_text_from_span = correct_feedback_span.get_text(
                    separator=" ", strip=True
                )

                # Jeśli tekst zawiera "Poprawna odpowiedź to:", wyodrębniamy ją
                if "Poprawna odpowiedź to:" in feedback_text_from_span:
                    extracted_ans = feedback_text_from_span.split(
                        "Poprawna odpowiedź to:", 1
                    )[1].strip()
                    if extracted_ans.endswith("."):  # Usuń kropkę na końcu, jeśli jest
                        extracted_ans = extracted_ans[:-1].strip()

                    if extracted_ans and extracted_ans not in correct_answers:
                        # Próbujemy dopasować wyodrębnioną odpowiedź do jednej z opcji
                        found_match_in_all = False
                        for ans_option in all_answers:
                            if (
                                extracted_ans.lower() in ans_option.lower()
                                or ans_option.lower() in extracted_ans.lower()
                            ):
                                if ans_option not in correct_answers:
                                    correct_answers.append(ans_option)
                                found_match_in_all = True
                                break
                        # Jeśli nie znaleziono dopasowania wśród opcji, dodajemy tekst bezpośrednio
                        if (
                            not found_match_in_all
                            and extracted_ans not in correct_answers
                        ):
                            correct_answers.append(extracted_ans)
                # Obsługa, gdy sama zawartość correct_feedback_span to poprawna odpowiedź
                elif (
                    feedback_text_from_span
                    and "Twoja odpowiedź jest poprawna" not in feedback_text_from_span
                    and feedback_text_from_span not in correct_answers
                ):
                    correct_answers.append(feedback_text_from_span)

            # W rzadkich przypadkach feedback może być w div.feedback bez span.correct
            general_feedback_div = outcome_div.find("div", class_="feedback")
            if (
                general_feedback_div
                and "Poprawna odpowiedź to:" in general_feedback_div.get_text()
            ):
                extracted_ans = (
                    general_feedback_div.get_text(separator=" ", strip=True)
                    .split("Poprawna odpowiedź to:", 1)[1]
                    .strip()
                )
                if extracted_ans.endswith("."):
                    extracted_ans = extracted_ans[:-1].strip()
                if extracted_ans and extracted_ans not in correct_answers:
                    found_match_in_all = False
                    for ans_option in all_answers:
                        if (
                            extracted_ans.lower() in ans_option.lower()
                            or ans_option.lower() in extracted_ans.lower()
                        ):
                            if ans_option not in correct_answers:
                                correct_answers.append(ans_option)
                            found_match_in_all = True
                            break
                    if not found_match_in_all and extracted_ans not in correct_answers:
                        correct_answers.append(extracted_ans)

        # Upewnij się, że nie ma duplikatów i są unikalne odpowiedzi
        correct_answers = list(set(correct_answers))
        all_answers = list(set(all_answers))

        questions_data.append(
            {
                "question_text": question_text,
                "all_answers": all_answers,
                "correct_answers": correct_answers,
            }
        )
    return questions_data


def generate_pdf(output_pdf_path, questions_list):
    """
    Generuje plik PDF z wyodrębnionymi pytaniami i odpowiedziami.
    """
    doc = SimpleDocTemplate(output_pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Definiowanie stylów z użyciem zarejestrowanej czcionki lub fallbacku
    # Używamy zmiennej FONT_NAME, która jest ustawiana globalnie po próbie rejestracji.
    question_style = styles["Normal"]
    # Jeśli FONT_NAME to 'DejaVuSans', użyjemy 'DejaVuSans-Bold', inaczej 'Helvetica-Bold'
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

    for q_data in questions_list:
        if not q_data["question_text"].strip():  # Pomiń pytania bez tekstu
            continue

        story.append(Paragraph("<b>Pytanie:</b>", question_style))
        story.append(Paragraph(q_data["question_text"], question_style))
        story.append(Spacer(1, 6))

        if q_data["all_answers"]:
            story.append(Paragraph("<b>Dostępne odpowiedzi:</b>", answer_style))
            for ans in q_data["all_answers"]:
                # Sprawdź, czy dana odpowiedź jest poprawna i pokoloruj ją
                if ans in q_data["correct_answers"]:
                    story.append(Paragraph(f"- {ans}", correct_answer_style))
                else:
                    story.append(Paragraph(f"- {ans}", answer_style))
            story.append(Spacer(1, 6))

        if q_data["correct_answers"]:
            story.append(Paragraph("<b>Poprawna odpowiedź:</b>", correct_answer_style))
            for corr_ans in q_data["correct_answers"]:
                story.append(Paragraph(f"- {corr_ans}", correct_answer_style))
        else:
            story.append(
                Paragraph(
                    "<b>Poprawna odpowiedź:</b> (nie udało się zidentyfikować lub brak)",
                    answer_style,
                )
            )

        story.append(Spacer(1, 12))  # Dodatkowy odstęp między pytaniami
        story.append(
            PageBreak()
        )  # Każde pytanie na nowej stronie dla lepszej czytelności

    try:
        doc.build(story)
        print(f"Pomyślnie wygenerowano plik PDF: {output_pdf_path}")
    except Exception as e:
        print(f"Wystąpił błąd podczas generowania pliku PDF: {e}")


if __name__ == "__main__":
    # --- Konfiguracja ścieżek ---
    html_files_directory = "quiz_4"
    output_pdf_name = "result_pdf/Quiz4_Pytania_i_Odpowiedzi.pdf"
    # --- Konfiguracja End ---

    all_questions = []

    if not os.path.exists(html_files_directory):
        print(f"Błąd: Katalog '{html_files_directory}' nie istnieje.")
        print("Utwórz katalog i umieść w nim pliki HTML z przeglądami quizów.")
    else:
        for filename in os.listdir(html_files_directory):
            if filename.endswith(".html"):
                file_path = os.path.join(html_files_directory, filename)
                print(f"Przetwarzam plik: {filename}")
                questions = parse_moodle_quiz_review(file_path)
                all_questions.extend(questions)

        if all_questions:
            print(f"Znaleziono łącznie {len(all_questions)} pytań.")
            generate_pdf(output_pdf_name, all_questions)
        else:
            print(
                "Nie znaleziono żadnych pytań do przetworzenia. Sprawdź, czy pliki HTML są poprawne i mają oczekiwaną strukturę Moodle."
            )
