"""Search streaming (SSE) endpoint tests.

用法:
    cd backend
    uv run python -m pytest ../test/test_search_stream.py -v

前提: 后端已启动 (http://localhost:8777)，且至少有一个已索引的数据集
"""

from __future__ import annotations

import json
import os

import pytest
import requests

BASE = os.environ.get("GRAPHARG_API_BASE", "http://localhost:8777/api")
SEARCH_TIMEOUT = 180  # search may take up to 3 minutes


# ── Helpers ───────────────────────────────────────────────────────────────


def parse_sse_events(response: requests.Response) -> list[dict]:
    """Parse SSE events from a streaming response.

    Returns a list of dicts: {"event": str, "data": dict | str}
    """
    events = []
    current_event = ""
    current_data = ""

    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue

        line = raw_line.strip() if isinstance(raw_line, str) else raw_line.decode("utf-8").strip()

        if line == "":
            # Empty line = end of event block
            if current_event or current_data:
                data_parsed = current_data
                try:
                    data_parsed = json.loads(current_data)
                except (json.JSONDecodeError, TypeError):
                    pass
                events.append({"event": current_event, "data": data_parsed})
                current_event = ""
                current_data = ""
            continue

        if line.startswith("event: "):
            current_event = line[len("event: "):]
        elif line.startswith("data: "):
            current_data = line[len("data: "):]

    # Handle last event if stream ended without trailing newline
    if current_event or current_data:
        try:
            data_parsed = json.loads(current_data)
        except (json.JSONDecodeError, TypeError):
            data_parsed = current_data
        events.append({"event": current_event, "data": data_parsed})

    return events


def find_event(events: list[dict], event_type: str) -> dict | None:
    """Find the first event with the given type."""
    for e in events:
        if e["event"] == event_type:
            return e
    return None


def find_all_events(events: list[dict], event_type: str) -> list[dict]:
    """Find all events with the given type."""
    return [e for e in events if e["event"] == event_type]


def stream_search(dataset_id: str, query: str, mode: str, **kwargs):
    """POST to the search/stream endpoint with streaming enabled."""
    return requests.post(
        f"{BASE}/datasets/{dataset_id}/search/stream",
        json={"query": query, "mode": mode},
        stream=True,
        timeout=kwargs.get("timeout", SEARCH_TIMEOUT),
    )


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def api():
    """Verify backend is reachable."""
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        r.raise_for_status()
    except requests.ConnectionError:
        pytest.skip(f"Backend not reachable at {BASE}")
    return BASE


@pytest.fixture(scope="module")
def indexed_dataset(api):
    """Find an indexed dataset for search tests."""
    r = requests.get(f"{api}/datasets")
    datasets = r.json().get("datasets", [])
    for ds in datasets:
        if ds.get("has_index") or ds.get("entity_count", 0) > 0:
            return ds["id"]
    pytest.skip("No indexed dataset available for search stream tests")


# ══════════════════════════════════════════════════════════════════════════
#  Tests
# ══════════════════════════════════════════════════════════════════════════


class TestSearchStreamFormat:
    """Test SSE response format and headers."""

    def test_response_headers(self, api, indexed_dataset):
        """SSE endpoint should return correct content-type headers."""
        r = stream_search(indexed_dataset, "test", "basic")
        try:
            assert r.status_code == 200
            content_type = r.headers.get("content-type", "")
            assert "text/event-stream" in content_type, (
                f"Expected text/event-stream, got {content_type}"
            )
            cache_control = r.headers.get("cache-control", "")
            assert "no-cache" in cache_control
        finally:
            r.close()

    def test_events_are_well_formed(self, api, indexed_dataset):
        """All SSE events should have 'event:' and 'data:' fields with valid JSON."""
        r = stream_search(indexed_dataset, "什么是知识图谱？", "basic")
        try:
            events = parse_sse_events(r)
            assert len(events) > 0, "Expected at least one SSE event"

            for ev in events:
                assert "event" in ev, f"Event missing 'event' field: {ev}"
                assert "data" in ev, f"Event missing 'data' field: {ev}"
                assert ev["event"] in ("status", "chunk", "done", "error"), (
                    f"Unexpected event type: {ev['event']}"
                )
                # data should be parsed as dict (valid JSON)
                assert isinstance(ev["data"], dict), (
                    f"Event data should be a dict, got {type(ev['data'])}: {ev['data']}"
                )
        finally:
            r.close()

    def test_event_sequence(self, api, indexed_dataset):
        """Successful search should emit: status* → chunk → done."""
        r = stream_search(indexed_dataset, "什么是知识图谱？", "basic")
        try:
            events = parse_sse_events(r)
            event_types = [e["event"] for e in events]

            # Must have at least one status, one chunk, and one done
            assert "status" in event_types, f"No 'status' event in {event_types}"
            assert "chunk" in event_types or "error" in event_types, (
                f"No 'chunk' or 'error' event in {event_types}"
            )

            # If successful, 'done' must come last
            if "done" in event_types:
                assert event_types[-1] == "done", (
                    f"'done' should be the last event, got: {event_types}"
                )

            # 'chunk' must come before 'done'
            if "chunk" in event_types and "done" in event_types:
                chunk_idx = event_types.index("chunk")
                done_idx = event_types.index("done")
                assert chunk_idx < done_idx
        finally:
            r.close()


class TestSearchStreamStatusEvents:
    """Test that status events report progress correctly."""

    def test_status_preparing(self, api, indexed_dataset):
        """First status event should be 'preparing'."""
        r = stream_search(indexed_dataset, "测试查询", "basic")
        try:
            events = parse_sse_events(r)
            status_events = find_all_events(events, "status")
            assert len(status_events) >= 1, "Expected at least one status event"

            first_status = status_events[0]["data"]
            assert "status" in first_status
            assert "message" in first_status
            assert first_status["status"] == "preparing", (
                f"First status should be 'preparing', got '{first_status['status']}'"
            )
        finally:
            r.close()

    def test_status_searching(self, api, indexed_dataset):
        """Should emit a 'searching' status after 'preparing'."""
        r = stream_search(indexed_dataset, "测试查询", "basic")
        try:
            events = parse_sse_events(r)
            status_events = find_all_events(events, "status")

            statuses = [e["data"]["status"] for e in status_events]
            assert "searching" in statuses, (
                f"Expected 'searching' status in {statuses}"
            )

            # 'preparing' should come before 'searching'
            if "preparing" in statuses:
                assert statuses.index("preparing") < statuses.index("searching")
        finally:
            r.close()


class TestSearchStreamModes:
    """Test all three search modes via SSE."""

    def test_basic_mode(self, api, indexed_dataset):
        """Basic RAG search via SSE should return a valid answer."""
        r = stream_search(indexed_dataset, "什么是知识图谱？", "basic")
        try:
            events = parse_sse_events(r)

            done = find_event(events, "done")
            error = find_event(events, "error")

            if done:
                data = done["data"]
                assert data["mode"] == "basic"
                assert data["query"] == "什么是知识图谱？"
                assert len(data["answer"]) > 0, "Answer should not be empty"

                # chunk text should match done answer
                chunk = find_event(events, "chunk")
                if chunk:
                    assert chunk["data"]["text"] == data["answer"]
            elif error:
                # Acceptable if index is incomplete — error should have a message
                assert "message" in error["data"]
                assert len(error["data"]["message"]) > 0
            else:
                pytest.fail("Expected either 'done' or 'error' event")
        finally:
            r.close()

    def test_local_mode(self, api, indexed_dataset):
        """Local search via SSE should complete."""
        r = stream_search(indexed_dataset, "描述主要实体", "local")
        try:
            events = parse_sse_events(r)

            done = find_event(events, "done")
            error = find_event(events, "error")

            assert done or error, "Expected 'done' or 'error' event"

            if done:
                assert done["data"]["mode"] == "local"
                assert len(done["data"]["answer"]) > 0
        finally:
            r.close()

    def test_global_mode(self, api, indexed_dataset):
        """Global search via SSE should complete."""
        r = stream_search(indexed_dataset, "概述主要概念", "global")
        try:
            events = parse_sse_events(r)

            done = find_event(events, "done")
            error = find_event(events, "error")

            assert done or error, "Expected 'done' or 'error' event"

            if done:
                assert done["data"]["mode"] == "global"
                assert len(done["data"]["answer"]) > 0
        finally:
            r.close()


class TestSearchStreamErrors:
    """Test error handling in SSE stream."""

    def test_invalid_mode(self, api, indexed_dataset):
        """Invalid mode should return HTTP 422 (Pydantic validation)."""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search/stream",
            json={"query": "test", "mode": "invalid_mode"},
            stream=True,
            timeout=10,
        )
        try:
            # FastAPI returns 422 for invalid enum/pattern
            assert r.status_code == 422, (
                f"Expected 422 for invalid mode, got {r.status_code}"
            )
        finally:
            r.close()

    def test_nonexistent_dataset(self, api):
        """Search on nonexistent dataset should yield an error SSE event or 404."""
        r = stream_search("nonexistent_dataset_xyz", "test", "basic")
        try:
            if r.status_code == 200:
                # Stream opened — should contain an error event
                events = parse_sse_events(r)
                error = find_event(events, "error")
                assert error is not None, (
                    "Expected error event for nonexistent dataset"
                )
                assert "message" in error["data"]
            else:
                # Or the endpoint might reject early
                assert r.status_code in (404, 422)
        finally:
            r.close()

    def test_missing_query(self, api, indexed_dataset):
        """Empty query should return HTTP 422."""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search/stream",
            json={"query": "", "mode": "basic"},
            stream=True,
            timeout=10,
        )
        try:
            assert r.status_code == 422, (
                f"Expected 422 for empty query, got {r.status_code}"
            )
        finally:
            r.close()

    def test_missing_body(self, api, indexed_dataset):
        """No request body should return HTTP 422."""
        r = requests.post(
            f"{api}/datasets/{indexed_dataset}/search/stream",
            stream=True,
            timeout=10,
        )
        try:
            assert r.status_code == 422
        finally:
            r.close()

    def test_incomplete_index_error(self, api):
        """Search on a dataset without index should yield an error event."""
        # Find a dataset without index, or create a temporary one
        r = requests.get(f"{api}/datasets")
        datasets = r.json().get("datasets", [])
        unindexed = [ds for ds in datasets if not ds.get("has_index")]

        if not unindexed:
            # Create a dataset without indexing it
            cr = requests.post(
                f"{api}/datasets",
                json={"name": "test_stream_unindexed"},
            )
            if cr.status_code != 200:
                pytest.skip("Cannot create test dataset")
            ds_id = cr.json()["id"]
        else:
            ds_id = unindexed[0]["id"]

        try:
            r = stream_search(ds_id, "test", "local")
            try:
                events = parse_sse_events(r)
                error = find_event(events, "error")
                assert error is not None, (
                    "Expected error event for unindexed dataset"
                )
                msg = error["data"]["message"]
                assert "不可用" in msg or "不完整" in msg or "missing" in msg.lower(), (
                    f"Error message should mention incomplete index: {msg}"
                )
            finally:
                r.close()
        finally:
            # Clean up created dataset
            if not unindexed:
                requests.delete(f"{api}/datasets/{ds_id}")


class TestSearchStreamChunk:
    """Test chunk event content."""

    def test_chunk_contains_text(self, api, indexed_dataset):
        """Chunk event should have a 'text' field with non-empty content."""
        r = stream_search(indexed_dataset, "什么是知识图谱？", "basic")
        try:
            events = parse_sse_events(r)
            chunks = find_all_events(events, "chunk")

            if chunks:
                for chunk in chunks:
                    assert "text" in chunk["data"], "Chunk missing 'text' field"
                    assert isinstance(chunk["data"]["text"], str)
                    assert len(chunk["data"]["text"]) > 0, "Chunk text should not be empty"
        finally:
            r.close()

    def test_done_contains_all_fields(self, api, indexed_dataset):
        """Done event should contain query, mode, answer, and time fields."""
        r = stream_search(indexed_dataset, "测试", "basic")
        try:
            events = parse_sse_events(r)
            done = find_event(events, "done")

            if done:
                data = done["data"]
                assert "query" in data, "Done event missing 'query'"
                assert "mode" in data, "Done event missing 'mode'"
                assert "answer" in data, "Done event missing 'answer'"
                assert "time" in data, "Done event missing 'time'"
                assert data["query"] == "测试"
                assert data["mode"] == "basic"
        finally:
            r.close()


class TestSearchStreamConsistency:
    """Test that streaming and non-streaming endpoints return consistent results."""

    def test_stream_matches_non_stream(self, api, indexed_dataset):
        """SSE done.answer should be comparable to non-streaming search answer.

        Note: LLM responses are non-deterministic, so we only verify both
        produce non-empty answers of similar magnitude rather than exact match.
        """
        query = "什么是知识图谱？"
        mode = "basic"

        # Non-streaming
        r_sync = requests.post(
            f"{api}/datasets/{indexed_dataset}/search",
            json={"query": query, "mode": mode},
            timeout=SEARCH_TIMEOUT,
        )
        if r_sync.status_code != 200:
            pytest.skip("Non-streaming search failed")
        sync_answer = r_sync.json()["answer"]

        # Streaming
        r_stream = stream_search(indexed_dataset, query, mode)
        try:
            events = parse_sse_events(r_stream)
            done = find_event(events, "done")
            if done:
                stream_answer = done["data"]["answer"]

                # Both should be non-empty
                assert len(sync_answer) > 0, "Non-streaming answer is empty"
                assert len(stream_answer) > 0, "Streaming answer is empty"

                # Length should be in the same ballpark (within 3x)
                ratio = len(stream_answer) / len(sync_answer)
                assert 0.33 < ratio < 3.0, (
                    f"Answer length ratio {ratio:.2f} out of range "
                    f"(stream={len(stream_answer)}, sync={len(sync_answer)})"
                )
        finally:
            r_stream.close()
