from what_to_eat_bot.application.normalization import normalize_text, parse_ingredient_list


def test_normalize_case_spaces_unicode_and_yo() -> None:
    assert normalize_text("  КУРИНАЯ   ГРУДКА! ") == "куриная грудка"
    assert normalize_text("Ёжик") == "ежик"


def test_parse_list_deduplicates_normalized_values() -> None:
    assert parse_ingredient_list(" Курица, лук; КУРИЦА\nморковь ") == [
        "Курица",
        "лук",
        "морковь",
    ]


def test_parse_list_accepts_one_ingredient_per_line() -> None:
    assert parse_ingredient_list("Курица\nЛук\nМорковь") == [
        "Курица",
        "Лук",
        "Морковь",
    ]
