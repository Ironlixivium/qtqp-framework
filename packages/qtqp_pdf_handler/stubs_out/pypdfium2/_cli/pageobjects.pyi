from _typeshed import Incomplete
from pypdfium2._cli._parsers import (
    add_input as add_input,
    add_n_digits as add_n_digits,
    get_input as get_input,
    iterator_hasvalue as iterator_hasvalue,
    round_list as round_list,
)

PARAM_POS: str
PARAM_IMGINFO: str
INFO_PARAMS: Incomplete

def attach(parser) -> None: ...
def print_img_metadata(m, n_digits, pad: str = "") -> None: ...
def main(args) -> None: ...
