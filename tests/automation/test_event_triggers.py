"""Tests for Event Triggers (G25.12)."""
import unittest
from jarvis.automation.triggers import (
    EventDefinition, Event, ConditionEvaluator, EventRouter,
)


class TestConditionEvaluator(unittest.TestCase):

    def setUp(self):
        self.eval = ConditionEvaluator()

    def test_greater_than(self):
        self.assertTrue(self.eval.evaluate("disk_usage > 90", {"disk_usage": 95}))
        self.assertFalse(self.eval.evaluate("disk_usage > 90", {"disk_usage": 80}))

    def test_less_than(self):
        self.assertTrue(self.eval.evaluate("temp < 50", {"temp": 40}))

    def test_equals(self):
        self.assertTrue(self.eval.evaluate("status == 1", {"status": 1}))

    def test_missing_field_returns_false(self):
        self.assertFalse(self.eval.evaluate("missing > 0", {}))

    def test_invalid_operator_returns_false(self):
        self.assertFalse(self.eval.evaluate("x ~~ 5", {"x": 5}))

    def test_malformed_condition_returns_false(self):
        self.assertFalse(self.eval.evaluate("bad", {}))
        self.assertFalse(self.eval.evaluate("a > b > c", {}))


class TestEventRouter(unittest.TestCase):

    def test_event_routes_to_bound_job(self):
        router = EventRouter()
        edef = EventDefinition(source="system", condition="disk_usage > 90")
        router.bind(edef, "disk-warning-job")

        event = Event(source="system", condition="disk_usage > 90",
                      payload={"disk_usage": 95})

        jobs = router.route(event, [edef])
        self.assertEqual(jobs, ["disk-warning-job"])

    def test_event_does_not_route_when_condition_fails(self):
        router = EventRouter()
        edef = EventDefinition(source="system", condition="disk_usage > 90")
        router.bind(edef, "disk-warning-job")

        event = Event(source="system", condition="disk_usage > 90",
                      payload={"disk_usage": 50})

        jobs = router.route(event, [edef])
        self.assertEqual(jobs, [])

    def test_event_cannot_grant_authority(self):
        """Invariant Z: event is data, not authorization.
        Even if event matches, routing just returns job_id.
        Authorization is checked separately by the scheduler."""
        router = EventRouter()
        edef = EventDefinition(source="system", condition="disk_usage > 90")
        router.bind(edef, "disk-warning-job")

        event = Event(source="system", condition="disk_usage > 90",
                      payload={"disk_usage": 95})

        jobs = router.route(event, [edef])
        # Router only returns job IDs. It has no concept of authorization.
        # The scheduler must still verify authorization before execution.
        self.assertIsInstance(jobs, list)
        self.assertEqual(len(jobs), 1)

    def test_event_cannot_modify_job_arguments(self):
        """Invariant Z: event payload never alters job arguments.
        The router returns job_ids only — no argument injection."""
        router = EventRouter()
        edef = EventDefinition(source="system", condition="disk_usage > 90")
        router.bind(edef, "disk-warning-job")

        # Malicious payload with extra fields
        event = Event(source="system", condition="disk_usage > 90",
                      payload={"disk_usage": 95, "inject": "rm -rf /"})

        jobs = router.route(event, [edef])
        # Router returns only job_id strings, never touches arguments
        self.assertEqual(jobs, ["disk-warning-job"])

    def test_source_mismatch_no_route(self):
        router = EventRouter()
        edef = EventDefinition(source="network", condition="status == 0")
        router.bind(edef, "net-job")

        event = Event(source="disk", condition="status == 0",
                      payload={"status": 0})

        jobs = router.route(event, [edef])
        self.assertEqual(jobs, [])

    def test_unbind_removes_routing(self):
        router = EventRouter()
        edef = EventDefinition(source="system", condition="disk_usage > 90")
        router.bind(edef, "disk-warning-job")
        router.unbind(edef.event_id)

        event = Event(source="system", condition="disk_usage > 90",
                      payload={"disk_usage": 95})

        jobs = router.route(event, [edef])
        self.assertEqual(jobs, [])


if __name__ == '__main__':
    unittest.main()
