from pypdfium2._cli._parsers import add_input as add_input, get_input as get_input, parse_numtext as parse_numtext

ACTION_LIST: str
ACTION_EXTRACT: str
ACTION_EDIT: str

def attach(parser) -> None: ...
def main(args) -> None: ...
