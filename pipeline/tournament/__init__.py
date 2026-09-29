"""Tournament stub (SPEC section 11): bracket schema and a generic simulator. The features built on top of it come later."""
from .bracket import Bracket, PlayIn, Region, Slot, standard_bracket  # noqa: F401
from .simulate import simulate_bracket  # noqa: F401
