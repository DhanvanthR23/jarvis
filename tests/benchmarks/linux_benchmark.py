"""Linux Benchmark suite (G19).

Evaluates the agent's ability to diagnose and propose fixes for common Linux issues.
"""
import os
import sys

# Ensure jarvis is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from jarvis.core.controller import JarvisController
from jarvis.core.events import EventType

BENCHMARK_SCENARIOS = [
    {
        'name': 'Wi-Fi diagnosis',
        'prompt': 'My wifi is dropping connection constantly. Diagnose the issue.',
        'expected_tools': ['command.execute', 'network.interfaces']
    },
    {
        'name': 'Bluetooth diagnosis',
        'prompt': 'My bluetooth headset is not connecting. Check bluetooth status.',
        'expected_tools': ['command.execute']
    },
    {
        'name': 'CPU issue',
        'prompt': 'The system is very slow, check for CPU hogs.',
        'expected_tools': ['processes.list']
    },
    {
        'name': 'RAM issue',
        'prompt': 'Check if the system is running out of memory.',
        'expected_tools': ['command.execute'] # e.g. free
    },
    {
        'name': 'Disk usage',
        'prompt': 'I am running out of disk space, find out what partitions are full.',
        'expected_tools': ['command.execute'] # e.g. df
    },
    {
        'name': 'Systemd failure',
        'prompt': 'Check if any systemd services have failed recently.',
        'expected_tools': ['command.execute', 'logs.search']
    },
    {
        'name': 'Log analysis',
        'prompt': 'Search the journal for sshd authentication failures.',
        'expected_tools': ['logs.search']
    },
    {
        'name': 'Configuration fix proposal',
        'prompt': 'Propose a fix for a badly configured sshd_config that allows root login.',
        'expected_tools': ['files.read']
    }
]

def run_benchmark(agent_backend, verbose=True):
    """Run the benchmark scenarios against a provided agent backend."""
    from jarvis.policy.manifest import load_manifest
    from jarvis.policy.trusted_hash import load_trusted_hash
    from jarvis.policy.engine import PolicyEngine
    from jarvis.tools.registry import register_readonly_tools
    import jarvis.tools.registry as registry
    
    # Setup policy
    manifest_path = 'jarvis/policy/capabilities.toml'
    hash_path = 'jarvis/policy/capabilities.hash'
    trusted_hash = load_trusted_hash(hash_path)
    manifest = load_manifest(manifest_path, trusted_hash)
    policy_engine = PolicyEngine(manifest)
    
    ctrl = JarvisController(
        agent_backend=agent_backend,
        policy_engine=policy_engine
    )
    register_readonly_tools(ctrl)
    
    # Also register commands (Level 2)
    from jarvis.tools import commands
    ctrl.register_tool('command.execute', commands.command_execute, 'Execute allowlisted commands')
    
    results = []
    
    print(f"Starting Linux Benchmark with {agent_backend.__class__.__name__}...")
    
    for scenario in BENCHMARK_SCENARIOS:
        if verbose:
            print(f"\n--- Scenario: {scenario['name']} ---")
            print(f"Prompt: {scenario['prompt']}")
            
        # Reset session for clean event tracking
        ctrl._session = ctrl._session.__class__()
        
        response = ctrl.process_request(scenario['prompt'])
        
        # Extract tools called
        tools_called = [e.data['tool_name'] for e in ctrl.session.events if e.type == EventType.TOOL_CALL]
        
        # Verify if expected tools were called
        success = False
        for expected in scenario['expected_tools']:
            if expected in tools_called:
                success = True
                break
                
        if verbose:
            print(f"Tools called: {tools_called}")
            print(f"Success: {'PASS' if success else 'FAIL'}")
            
        results.append({
            'scenario': scenario['name'],
            'success': success,
            'tools_called': tools_called
        })
        
    score = sum(1 for r in results if r['success'])
    total = len(BENCHMARK_SCENARIOS)
    print(f"\n=== Benchmark Complete: {score}/{total} Passed ===")
    return results

if __name__ == '__main__':
    # By default run with MockAgent for CI
    from jarvis.agent.mock import MockAgent, ScriptedScenario, ScriptedStep
    
    mock_scenarios = [
        ScriptedScenario('wifi', [ScriptedStep('command.execute', {'command': 'nmcli'})], 'done'),
        ScriptedScenario('bluetooth', [ScriptedStep('command.execute', {'command': 'bluetoothctl'})], 'done'),
        ScriptedScenario('slow', [ScriptedStep('processes.list', {})], 'done'),
        ScriptedScenario('memory', [ScriptedStep('command.execute', {'command': 'free'})], 'done'),
        ScriptedScenario('disk', [ScriptedStep('command.execute', {'command': 'df'})], 'done'),
        ScriptedScenario('systemd services', [ScriptedStep('logs.search', {'grep': 'failed'})], 'done'),
        ScriptedScenario('authentication failures', [ScriptedStep('logs.search', {'service': 'sshd'})], 'done'),
        ScriptedScenario('sshd_config', [ScriptedStep('files.read', {'path': '/etc/ssh/sshd_config'})], 'done'),
    ]
    agent = MockAgent(mock_scenarios)
    run_benchmark(agent)
