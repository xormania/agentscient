"""Every planted fault of the ladder driver, one set for the side-by-side
records that retire files: the three tables together must catch what the
retired files caught."""

from ops.conductor.tests.ladder_faults import MUTANTS as TABLES
from ops.conductor.tests.ladder_faults_refusals import MUTANTS as REFUSALS
from ops.conductor.tests.ladder_faults_stops import MUTANTS as STOPS

MUTANTS = [*TABLES, *REFUSALS, *STOPS]
