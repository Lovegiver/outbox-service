from pytest_bdd import scenarios

from tests.bdd.steps.authentication_steps import *  # noqa: F403,F401
from tests.bdd.steps.event_type_steps import *  # noqa: F403,F401
from tests.bdd.steps.project_member_steps import *  # noqa: F403,F401
from tests.bdd.steps.project_steps import *  # noqa: F403,F401
from tests.bdd.steps.response_steps import *  # noqa: F403,F401
from tests.bdd.steps.route_steps import *  # noqa: F403,F401
from tests.bdd.steps.user_steps import *  # noqa: F403,F401


scenarios("features/routes.feature")
