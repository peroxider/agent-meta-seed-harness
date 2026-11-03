# ADR 045: Cooperative scheduling at Host call boundaries

Date: 2026-10-30
Status: accepted; cooperative trusted profile only

## Observation and decision

A complete installed-wheel Seed run exposed an SDK Hello deadline during 100
Context projections over one frozen Task. The Context test passed alone. Each
projection coroutine completed synchronous store work without suspension; a
consumer awaiting it repeatedly could therefore delay the daemon's ready I/O
and management coroutines. Immediate fake model/PURE callbacks have the same
scheduling property.

The three async Host facade operations (project_context, invoke_model and
invoke_tool) now yield to the event loop before checking cancellation and
performing work. The scheduling point is outside every store transaction and
before any grant/budget reservation or callback. Task state, deadline, issued
projection/call identity and authority checks still run after scheduling. No
transaction or writer lock spans this await. Cached projection identity and
confirmed-result replay rules are unchanged.

This is cooperative fairness between Host calls, not hard preemption: a trusted
callback can still block the event loop until it returns/awaits, and individual
synchronous store operations must remain bounded. No feature, protocol version,
Backend capability, Host SPI support or release status is promoted.

## Proofs

The scheduler-port unit regression interleaves ready work with 100 immediate
projections and verifies that ready cancellation wins before each of the three
operations can write/reserve/call. Real AMPAK and installed-wheel Context/Host
recovery/cancellation tests remain required. The port fixture itself does not
provide an execution or isolation proof.
