import threading

from zet.services.local_image_evaluation_service import LocalImageEvaluationService


def test_stage_publishes_every_gate_before_collecting_and_ranks_concurrently():
    service = LocalImageEvaluationService()
    staged = []
    collected = threading.Event()
    release_gate_collector = threading.Event()
    ranked = threading.Event()
    saved = []

    def stage_gates():
        staged.extend((candidate, gate) for candidate in ("one", "two") for gate in ("face", "framing"))

    def collect_gates():
        assert len(staged) == 4
        collected.set()
        release_gate_collector.wait(5)

    def rank():
        assert collected.is_set()
        ranked.set()

    service.stage_view_evaluation("run", "FRONT", "evaluation-1", stage_gates=stage_gates,
        collect_gates=collect_gates, rank=rank, save_evaluation=saved.append,
        input_hashes={"one": "hash-one", "two": "hash-two"})

    assert collected.wait(2)
    assert ranked.wait(2)
    assert staged == [("one", "face"), ("one", "framing"), ("two", "face"), ("two", "framing")]
    assert saved[0]["input_hashes"] == {"one": "hash-one", "two": "hash-two"}
    release_gate_collector.set()


def test_reconcile_restages_missing_jobs_once_after_restart():
    service = LocalImageEvaluationService()
    entered = threading.Event()
    ranked = threading.Event()
    release = threading.Event()
    calls = []

    def stage():
        calls.append("stage")

    def collect():
        entered.set()
        release.wait(5)

    def rank():
        calls.append("rank")
        ranked.set()

    assert service.reconcile_review_jobs("run", "BACK", "evaluation-2",
        stage_gates=stage, collect_gates=collect, rank=rank)
    assert entered.wait(2)
    assert ranked.wait(2)
    assert not service.reconcile_review_jobs("run", "BACK", "evaluation-2",
        stage_gates=stage, collect_gates=collect, rank=lambda: calls.append("duplicate rank"))
    assert calls.count("stage") == 1
    assert calls.count("rank") == 1
    release.set()
