import unicodedata

def normalize_input(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("normalize_input espera str")
    text = text.strip()
    text = text.casefold()  
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    if not text:
        raise ValueError("normalize_input: entrada vazia")
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
            raise AssertionError(f"aceitou tipo errado: {bad!r}")

    for empty in ("", "  "):
        try:
            normalize_input(empty)
        except ValueError:
            pass
        else:
            raise AssertionError(f"aceitou vazio: {empty!r}")

if __name__ == "__main__":
    run_kernel_tests()
    print("Text kernel tests: OK")
    
        

    