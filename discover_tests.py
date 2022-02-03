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

        if not self.pytest_args:
            self.pytest_args = [
                '-l',
                'tests/',
                '--cov=metREx/app',
                '--junitxml=test-results/results.xml'
            ]

            if self.verbose:
                self.pytest_args.append('--verbose')

        sys.exit(pytest.main(self.pytest_args))
