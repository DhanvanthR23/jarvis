import unittest
import sys
sys.argv = ['run_test.py']
from tests.automation.test_policy import TestAutomationPolicy
suite = unittest.TestSuite()
suite.addTest(TestAutomationPolicy('test_authorized_safe_job_allowed'))
res = unittest.TextTestRunner().run(suite)
