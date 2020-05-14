from setuptools.command.test import test


class DiscoverTest(test):
    def finalize_options(self):
        test.finalize_options(self)

        try:
            self.test_args = []
        except AttributeError:
            pass

        self.test_suite = True

    def initialize_options(self):
        test.initialize_options(self)

        self.pytest_args = []

    def run_tests(self):
        import pytest
        import sys

        from metREx.manage import run_scheduler

        if not self.pytest_args:
            self.pytest_args = [
                '-l',
                '--junitxml=test-results/results.xml', 'tests/unit', 'tests/integration'
            ]

            if self.verbose:
                self.pytest_args.append('--verbose')

        run_scheduler(False)

        sys.exit(pytest.main(self.pytest_args))
