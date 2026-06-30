# connector write probe

from pytest_bdd import given
from pytest_bdd import parsers

VALUE = 1

class Probe:
    pass


pattern = parsers.parse('a project exists')

@given(pattern)
def project_exists() -> None:
    return None
