import json


def naive_parse(chunks):
    """Replicates current naive newline-split parsing (fails on split JSON)."""
    events = []
    for chunk in chunks:
        for line in chunk.split("\n"):
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def buffered_parse(chunks):
    """Robust parser that buffers partial JSON lines across chunks."""
    events = []
    buffer = ""
    for chunk in chunks:
        buffer += chunk
        lines = buffer.split("\n")
        buffer = lines.pop() if lines else ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    tail = buffer.strip()
    if tail:
        events.append(json.loads(tail))
    return events


def main():
    payload = (
        '{"type":"metadata","conversation_id":"abc"}\n'
        '{"type":"content","content":"hello"}\n'
        '{"type":"done"}\n'
    )
    # Intentionally split in the middle of JSON tokens to simulate chunking
    chunks = [payload[:18], payload[18:37], payload[37:55], payload[55:]]

    print("Chunks:")
    for i, chunk in enumerate(chunks):
        print(f"  {i}: {repr(chunk)}")

    print("\nNaive parse (expected to fail on split JSON):")
    try:
        naive_events = naive_parse(chunks)
        print(f"  Unexpected success: {naive_events}")
    except Exception as exc:
        print(f"  Failed as expected: {exc}")

    print("\nBuffered parse (expected to succeed):")
    buffered_events = buffered_parse(chunks)
    print(f"  Parsed events: {buffered_events}")

    assert len(buffered_events) == 3, "Buffered parser should recover all events"
    assert buffered_events[1]["type"] == "content"
    print("\nPASS: Buffered parser handles chunked JSON lines.")


if __name__ == "__main__":
    main()
