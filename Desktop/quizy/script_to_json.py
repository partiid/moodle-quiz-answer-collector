import json
import os
import re  # Dodajemy import re dla lepszego czyszczenia tekstu

from bs4 import BeautifulSoup


def extract_answer_text(option_container):
    """
    Wyodrębnia czysty tekst odpowiedzi z kontenera opcji,
    usuwając numerację (a., b., ...) i zbędne frazy.
    """
    answer_label_div = option_container.find("div", class_="d-flex")
    if not answer_label_div:
        return ""

    # Klonujemy div, aby nie modyfikować oryginalnego obiektu BeautifulSoup
    cloned_answer_label_div = BeautifulSoup(str(answer_label_div), "html.parser")

    # Usuń span z numerem odpowiedzi (a., b., ...)
    answernumber_span = cloned_answer_label_div.find("span", class_="answernumber")
    if answernumber_span:
        answernumber_span.decompose()

    # Wyciągnij tekst, łącząc go spacjami
    option_text = cloned_answer_label_div.get_text(separator=" ", strip=True)

    # Usuń frazy, które Moodle dodaje do tekstu odpowiedzi w widoku przeglądu
    # Używamy re.sub dla większej elastyczności, ignorując wielkość liter.
    option_text = re.sub(
        r"Twoja odpowiedź jest poprawna\.", "", option_text, flags=re.IGNORECASE
    )
    option_text = re.sub(r"Wybrano\.", "", option_text, flags=re.IGNORECASE)
    option_text = re.sub(
        r"Oznaczone\.", "", option_text, flags=re.IGNORECASE
    )  # Dodatkowy tekst Moodle
    option_text = re.sub(
        r"Częściowo poprawna\.", "", option_text, flags=re.IGNORECASE
    )  # Dla częściowo poprawnych
    option_text = re.sub(
        r"Błędna\.", "", option_text, flags=re.IGNORECASE
    )  # Dla błędnych odpowiedzi
    option_text = re.sub(
        r"Prawidłowa odpowiedź\.", "", option_text, flags=re.IGNORECASE
    )  # Inna fraza Moodle
    option_text = re.sub(
        r"Prawidłowe odpowiedzi\.", "", option_text, flags=re.IGNORECASE
    )  # Inna fraza Moodle (mnoga)

    # Usuń podwójne spacje i ponownie obetnij
    option_text = re.sub(r"\s+", " ", option_text).strip()

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
            # Usuń flagi i inne zbędne elementy z pytania
            for flag_div in qtext_div.find_all("div", class_="questionflag"):
                flag_div.decompose()
            # Usuń paragrafy z oceną
            for grade_p in qtext_div.find_all("p", class_="grade"):
                grade_p.decompose()
            question_text = qtext_div.get_text(separator=" ", strip=True)
            question_text = re.sub(
                r"\s+", " ", question_text
            ).strip()  # Znormalizuj spacje

        # 2. Znajdź blok odpowiedzi i opcje
        answer_div = q_block.find("div", class_="answer")
        if answer_div:
            # Kontenery opcji to div z klasami 'r0' lub 'r1'
            # Dodatkowo, sprawdź 'r' ogólnie, jeśli klasa jest bardziej ogólna
            option_containers = answer_div.find_all(
                ["div"], class_=re.compile(r"r[01]")
            )

            for option_container in option_containers:
                option_text = extract_answer_text(option_container)

                if option_text and option_text not in all_answers:
                    all_answers.append(option_text)

                # 3. Sprawdź, czy odpowiedź jest poprawna
                is_this_option_correct = False

                # Poprawna odpowiedź ma klasę 'correct'
                if "correct" in option_container.get("class", []):
                    is_this_option_correct = True

                # Ikona zielonego checkmarka (Moodle często jej używa)
                if option_container.find("i", class_="fa-check"):
                    is_this_option_correct = True

                # Czasem jest wewnątrz feedbacku
                feedback_div_inside_option = option_container.find(
                    "div", class_="feedback"
                )
                if feedback_div_inside_option and (
                    "Twoja odpowiedź jest poprawna."
                    in feedback_div_inside_option.get_text()
                    or "Prawidłowa odpowiedź." in feedback_div_inside_option.get_text()
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
                    extracted_ans_raw = feedback_text_from_span.split(
                        "Poprawna odpowiedź to:", 1
                    )[1].strip()
                    # Usuń wszelkie "Błędna.", "Prawidłowa odpowiedź." itp. które mogły zostać
                    extracted_ans = re.sub(
                        r"(Twoja odpowiedź jest |Prawidłowa |Prawidłowe |Błędna\.|Wybrano\.)",
                        "",
                        extracted_ans_raw,
                        flags=re.IGNORECASE,
                    ).strip()
                    if extracted_ans.endswith("."):  # Usuń kropkę na końcu, jeśli jest
                        extracted_ans = extracted_ans[:-1].strip()

                    # Spróbuj dopasować do już zebranych odpowiedzi
                    found_match_in_all = False
                    for ans_option in all_answers:
                        # Dokładniejsze dopasowanie: pełna zgodność lub bardzo duża część
                        # Możesz tu dostosować próg dopasowania, jeśli potrzebujesz
                        if (
                            extracted_ans.lower() == ans_option.lower()
                            or (
                                len(extracted_ans) > 10
                                and extracted_ans.lower() in ans_option.lower()
                            )
                            or (
                                len(ans_option) > 10
                                and ans_option.lower() in extracted_ans.lower()
                            )
                        ):
                            if ans_option not in correct_answers:
                                correct_answers.append(ans_option)
                            found_match_in_all = True
                            break
                    # Jeśli nie znaleziono dopasowania wśród opcji, dodajemy tekst bezpośrednio
                    if (
                        not found_match_in_all
                        and extracted_ans
                        and extracted_ans not in correct_answers
                    ):
                        correct_answers.append(extracted_ans)

                # Obsługa, gdy sama zawartość correct_feedback_span to poprawna odpowiedź
                elif (
                    feedback_text_from_span
                    and "Twoja odpowiedź jest poprawna" not in feedback_text_from_span
                    and feedback_text_from_span not in correct_answers
                    and not re.search(
                        r"oceniono|punktów", feedback_text_from_span, re.IGNORECASE
                    )  # Ignoruj teksty o punktach
                ):
                    # Sprawdź, czy tekst jest sensowną odpowiedzią, a nie tylko oceną
                    if (
                        len(feedback_text_from_span.split()) > 2
                    ):  # Prosta heurystyka, że to nie jest tylko "Poprawna."
                        correct_answers.append(feedback_text_from_span)

            # W rzadkich przypadkach feedback może być w div.feedback bez span.correct
            general_feedback_div = outcome_div.find("div", class_="feedback")
            if (
                general_feedback_div
                and "Poprawna odpowiedź to:" in general_feedback_div.get_text()
            ):
                extracted_ans_raw = (
                    general_feedback_div.get_text(separator=" ", strip=True)
                    .split("Poprawna odpowiedź to:", 1)[1]
                    .strip()
                )
                extracted_ans = re.sub(
                    r"(Twoja odpowiedź jest |Prawidłowa |Prawidłowe |Błędna\.|Wybrano\.)",
                    "",
                    extracted_ans_raw,
                    flags=re.IGNORECASE,
                ).strip()

                if extracted_ans.endswith("."):
                    extracted_ans = extracted_ans[:-1].strip()
                if extracted_ans and extracted_ans not in correct_answers:
                    found_match_in_all = False
                    for ans_option in all_answers:
                        if (
                            extracted_ans.lower() == ans_option.lower()
                            or (
                                len(extracted_ans) > 10
                                and extracted_ans.lower() in ans_option.lower()
                            )
                            or (
                                len(ans_option) > 10
                                and ans_option.lower() in extracted_ans.lower()
                            )
                        ):
                            if ans_option not in correct_answers:
                                correct_answers.append(ans_option)
                            found_match_in_all = True
                            break
                    if (
                        not found_match_in_all
                        and extracted_ans
                        and extracted_ans not in correct_answers
                    ):
                        correct_answers.append(extracted_ans)

        # Upewnij się, że nie ma duplikatów i są unikalne odpowiedzi
        correct_answers = list(
            dict.fromkeys(correct_answers)
        )  # Zachowuje kolejność unikalnych
        all_answers = list(dict.fromkeys(all_answers))  # Zachowuje kolejność unikalnych

        questions_data.append(
            {
                "question_text": question_text,
                "all_answers": all_answers,
                "correct_answers": correct_answers,
            }
        )
    return questions_data


if __name__ == "__main__":
    # --- Konfiguracja ścieżek ---
    # Katalog główny, w którym znajdują się podkatalogi "quiz_X"
    base_directory = "modelowanie_procesow_biznesowych"
    output_json_file = "all_quiz_questions.json"  # Plik wyjściowy JSON
    # --- Konfiguracja End ---

    all_extracted_questions = []

    if not os.path.exists(base_directory):
        print(f"Błąd: Katalog '{base_directory}' nie istnieje.")
        print("Upewnij się, że katalog główny dla quizów jest poprawny.")
    else:
        # Przejrzyj wszystkie elementy w katalogu bazowym
        for item_name in os.listdir(base_directory):
            item_path = os.path.join(base_directory, item_name)

            # Sprawdź, czy element jest katalogiem i czy jego nazwa zaczyna się od "quiz"
            if os.path.isdir(item_path) and item_name.lower().startswith("quiz"):
                html_files_directory = (
                    item_path  # To jest teraz katalog z plikami HTML dla danego quizu
                )
                print(f"\n--- Przetwarzam katalog quizu: {html_files_directory} ---")

                for filename in os.listdir(html_files_directory):
                    if filename.endswith(".html"):
                        file_path = os.path.join(html_files_directory, filename)
                        print(f"  Przetwarzam plik: {filename}")
                        questions = parse_moodle_quiz_review(file_path)
                        all_extracted_questions.extend(questions)
            elif os.path.isfile(item_path) and item_name.lower().endswith(".html"):
                # Jeśli pliki HTML są bezpośrednio w katalogu bazowym, również je przetwórz
                print(
                    f"\n--- Przetwarzam plik HTML bezpośrednio w katalogu bazowym: {item_path} ---"
                )
                questions = parse_moodle_quiz_review(item_path)
                all_extracted_questions.extend(questions)

        if all_extracted_questions:
            print(
                f"\nZnaleziono łącznie {len(all_extracted_questions)} pytań ze wszystkich quizów."
            )

            # Zapisz do JSON
            try:
                with open(output_json_file, "w", encoding="utf-8") as f:
                    json.dump(all_extracted_questions, f, ensure_ascii=False, indent=4)
                print(
                    f"Wszystkie pytania zostały zapisane do pliku: {output_json_file}"
                )
            except Exception as e:
                print(f"Błąd podczas zapisu do pliku JSON: {e}")
        else:
            print(
                "Nie znaleziono żadnych pytań do przetworzenia. Sprawdź, czy pliki HTML są poprawne i mają oczekiwaną strukturę Moodle."
            )
