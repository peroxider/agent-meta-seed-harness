# ADR 051: Controlled Provider HTTPS edge and native worker ownership

Date: 2026-10-31
Status: internal implementation in progress; S04/RP-03/public-wheel proofs OPEN

## Decision

Provider HTTP execution belongs to a fixed Runtime-owned worker, not an
external Harness callback holding plaintext credentials. The internal transport
port carries a canonical bounded request, an exact model, protected credential
handle, HTTPS host/port/path, explicit IP networks and byte/output/time ceilings.
The Service execution token binds that request and Actor/Action/session/Realm/
Epoch. Concrete ceilings include one model call; a lesser signed ceiling cannot
authorize a larger request. The worker revalidates before native effects.

The HTTPS edge owns its verifying TLS context. DNS must return only authorized
addresses; mixed private/metadata answers are refused. It selects a deterministic
pinned address and connects directly with the approved hostname for SNI and
certificate checks. No second lookup, proxy environment discovery, redirects,
address fallback or automatic retry occurs. Public use currently requires the
implemented Windows DPAPI profile; an unknown/insecure credential implementation
cannot be promoted by a label. Test loopback policies remain CONTROLLED_TEST_ONLY.

Only enforcement resolves a provider-purpose item. Secret buffers are released
through the CredentialStore's zeroization scope. Responses are bounded JSON,
without upstream headers or raw exception diagnostics. Literal/JSON-escaped
credential echoes are refused. Python/TLS can retain immutable copies; this is
an OS process/account boundary, not a guarantee against a compromised same-user
process or hostile upstream encoding of a secret.

Failure before HTTP writing is NOT_SENT. Failure after a write may have started,
an incomplete response, timeout or an uncertain server/gateway error is UNKNOWN;
it must not cause another model request. Complete HTTP failures are bounded
observations, not permission for a retry or zero-cost settlement. Rate-limit
metadata is advisory. The bounded session cache preserves results/uncertainty
and rejects changes of payload or Actor/Action/session. It is not durable
recovery: admission, attempts, budget/effect reservation and terminal commit
must be journaled by the Host before/after the external await.

Windows workers must join an owner-only KILL_ON_JOB_CLOSE Job and close their
extra Job handle before READY. The parent verifies the actual worker PID's Job
membership before sending a request; Popen.pid may be a venv redirector. The
native Job layout and access checks follow the [Microsoft structure](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)
and [membership API](https://learn.microsoft.com/en-us/windows/win32/api/jobapi/nf-jobapi-isprocessinjob).
Linux entrypoints arm SIGKILL on creator-thread death and check the parent PID
before and after, following [PR_SET_PDEATHSIG](https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html).
Unsupported platforms fail closed. This lifetime mechanism is not a strong
execution or network sandbox and does not repair/declare the Portable Backend.

## Current evidence and remaining assembly

Real local TLS tests exercise signatures, DNS/IP policy, actual DPAPI purpose
binding, hostname/CA verification, bounded/error/credential-echo responses,
trickled headers, concurrent replay and disconnect uncertainty. Native process
tests observe actual Windows Job termination after forced owner death. A Linux
audit retains a PIDFD and observes a sleeping guarded child terminate after its
creator is SIGKILLed; wrong-parent entry is refused before READY. No paid
Provider credential or request is used in these tests.

The fixed single-request worker and bounded controller now use private canonical
control frames over stdin/stdout, a sanitized environment and no request data in
argv. The child joins native ownership before READY; the parent verifies the
actual PID and retains a Windows process handle or Linux PIDFD before sending.
The child independently rechecks the certificate/token before opening credential
storage. Only the child resolves a provider-purpose item. Result frames bind the
request ID and full scope hash. No package entrypoint or arbitrary command is
accepted by this worker.

Each controller is a fresh native session: old signed requests cannot restore
its volatile cache. Capacity and concurrent processes are bounded. Absolute
deadlines are part of the signed request and cover queueing/startup; cancellation
reaps the actual process before terminal observation. A port interruption carries
the outcome that the admitted caller must journal. Complete native outcomes
observed during cancellation are preserved; they never authorize subsequent
effects of a cancelled Task. Reaping uncertainty closes further admission.
Process tests exercise protected-handle/TLS requests, child signature rejection,
concurrent replay, cancellation, queue expiry, result binding, fresh sessions
and actual controller SIGKILL after a request reaches the test server.

The public Host Provider plan/normalizer bridge, operator credential registration
and profile binding, exact tokenizer/price
policies, the public binding of the [durable accounting foundation](052-durable-provider-invocation-accounting.md), recovery/cancellation proofs,
captured R2 response and authorized bounded live job remain required. The current
public API/Host execution profile is unchanged; none of these internal tests
closes RP-03 or establishes live Provider support.
