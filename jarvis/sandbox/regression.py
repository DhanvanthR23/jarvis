import fnmatch
import os
import unittest

SECURITY_SENSITIVE_PATHS = frozenset([
    'jarvis/sandbox/*',
    'jarvis/mcp/*',
    'jarvis/policy/*',
    'jarvis/tools/*',
    'capabilities.toml',
    'tests/sandbox/*'
])

def is_security_sensitive(changed_file: str) -> bool:
    """Check if a file path matches any security-sensitive pattern."""
    for pattern in SECURITY_SENSITIVE_PATHS:
        if fnmatch.fnmatch(changed_file, pattern):
            return True
    return False

def run_security_suite() -> bool:
    """Discovers and runs all tests under tests/sandbox/ and tests/security/."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    start_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    sandbox_dir = os.path.join(start_dir, 'tests', 'sandbox')
    security_dir = os.path.join(start_dir, 'tests', 'security')
    
    if os.path.exists(sandbox_dir):
        suite.addTests(loader.discover(sandbox_dir, pattern='test_*.py', top_level_dir=start_dir))
        
    if os.path.exists(security_dir):
        suite.addTests(loader.discover(security_dir, pattern='test_*.py', top_level_dir=start_dir))
        
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()
