import unicodedata

def normalize_input(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("normalize_input expects str")
    text = text.strip()
    text = text.casefold()  
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    if not text:
        raise ValueError("normalize_input: empty input")
    return text

def run_kernel_tests() -> None:
    assert normalize_input(" Fála ") == "fala"
    assert normalize_input("AÇÃO") == "acao"
    assert normalize_input("toque") == "toque"

    for bad in (123, None, True):
        try:
            normalize_input(bad)
        except TypeError:
            pass
        else:
            raise AssertionError(f"accepted wrong type: {bad!r}")

    for empty in ("", "  "):
        try:
            normalize_input(empty)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted empty: {empty!r}")

if __name__ == "__main__":
    run_kernel_tests()
    print("Text kernel tests: OK")
    
        

    
