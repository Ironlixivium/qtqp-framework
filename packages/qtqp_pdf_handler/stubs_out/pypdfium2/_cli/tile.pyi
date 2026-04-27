from enum import Enum
from pypdfium2._cli._parsers import add_input as add_input, get_input as get_input

class Units(Enum):
    PT = 0
    MM = 1
    CM = 2
    IN = 3

def units_to_pt(value, unit): ...
def attach(parser): ...
def main(args) -> None: ...
