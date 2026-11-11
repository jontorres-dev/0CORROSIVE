import importlib

MODULES = (
    "alpha001",
    "alpha001.ENGINE",
    "alpha001.ENGINE.deterministic",
    "alpha001.ENGINE.deterministic.World",
    "alpha001.ENGINE.deterministic.deny",
    "alpha001.ENGINE.deterministic.text",
    "alpha001.ENGINE.deterministic.verbs",
    "alpha001.ENGINE.deterministic.door",
)


def run_import_kernel_tests() -> None:
    for name in MODULES:
        importlib.import_module(name)
    deterministic = importlib.import_module("alpha001.ENGINE.deterministic")
    assert hasattr(deterministic, "World")
    print("Import kernel tests: OK")


if __name__ == "__main__":
    run_import_kernel_tests()
