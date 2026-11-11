from enum import Enum
    # 1. Verb CLASS
class Verb(str, Enum):
    TALK = "talk"
    TOUCH = "touch"
    ITEM = "item"
    SEARCH = "search"
    MOVE = "move"
    # WAIT = "wait"  # not used for now
    STOP = "stop"

    # 2. free text actions    
TXT_VERBS = {Verb.TOUCH, Verb.TALK, Verb.SEARCH}

 

def run_verb_kernel_tests() -> None:
     # 3. values 
    assert Verb.TALK.value == "talk"
    assert Verb.TOUCH.value == "touch"
    assert Verb.ITEM.value == "item"
    assert Verb.SEARCH.value == "search"
    assert Verb.MOVE.value == "move"
    # assert Verb.WAIT.value == "wait"
    assert Verb.STOP.value == "stop"
    assert Verb.TOUCH in TXT_VERBS
    assert Verb.TALK in TXT_VERBS
    assert Verb.SEARCH in TXT_VERBS
   
    # assert Verb("wait") is Verb.WAIT

    # 4. invalid value is rejected
    try:
        Verb("leave")
        raise AssertionError("leave should not exist")
    except ValueError:
        pass

    # 5. exact size
    assert len(Verb) == 6

    # 6.*********TEST
    print("Verb kernel OK")


if __name__ == "__main__":
    run_verb_kernel_tests()
