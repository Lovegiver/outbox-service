# connector write probe

from pytest_bdd import given
from pytest_bdd import parsers

VALUE = 1

class Probe:
    pass


@given('a project exists')
def project_exists() -> None:
    return None
