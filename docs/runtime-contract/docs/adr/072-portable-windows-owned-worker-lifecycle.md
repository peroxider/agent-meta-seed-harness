# ADR 072: Portable Windows worker identity, launch and cancellation

Status: Verified development candidate: all 1496 Root unit tests without module
exclusions; 381 installed Windows tests and 380 installed Linux tests plus one
Windows-only skip. After a PID-based test assumption was replaced by retained
process-object observation, the final focused 33-case suite and fresh installed
cohorts pass with identical runtime wheel bytes. Evidence:
`reports/portable-windows-v2-input/verification.json`. Current published pin is
the preceding Scratch retirement wheel, not these changes.

The original Windows Portable path used an unavailable `subprocess` suspended
flag, passed a process handle to `ResumeThread`/`TerminateJobObject`, lost its Job
handle, and read process identity only from `/proc`. Windows worker environments
also omitted the system directory required to initialize Winsock. These defects
caused the generic Portable/AgentOS baseline failures previously kept separate
from Scratch verification.

Windows identity now opens a non-inheritable SYNCHRONIZE/QUERY_LIMITED_INFORMATION
handle, requires the actual process object to be unsignalled and reads its
creation FILETIME. A retained handle to an exited process is not liveness. The
minimal environment obtains SystemRoot/WINDIR from Windows itself, prevents
case-insensitive overrides and retains the existing secret/proxy/home exclusions.

Portable uses the existing owner-only kill-on-close Job primitive with a fixed
`portable` kind. The parent retains its handle. The isolated-mode fixed worker
joins the Job before reading a request, handles venv redirector PID differences,
and the parent checks actual claimed-PID membership with the launch nonce before
recording ownership. A child that exits before claiming fails promptly even
when the injected ledger clock is fixed. No unsafe suspended-thread helper is
retained. No new untrusted-code, network-isolation or hard-quota claim is made.

Cancellation uses the retained Job handle after identity/membership validation.
It writes cooperative cancellation, waits for all Job members, then terminates
that exact Job if needed and confirms its active-process count reaches zero.
A process handle is never used as a Job, a recycled PID is not signalled, and
unavailable confirmation remains UNKNOWN. Already-terminal results remain
durable while residual-tree confirmation is reported separately. Unclaimed
startup cannot read a request after its Job closes. Finished Job handles are
reaped during subsequent submissions/session closure.

Tests use Python sleepers on both platforms rather than assume a POSIX `sleep`
binary exists. Windows tests observe the actual joined PID, retained exited
handles, wrong-identity refusal, force cancellation and descendant exit. Some
venv launchers reap their descendants when the leader exits; that permits
cooperative completion without unnecessary escalation, but an empty Job is
still required. Linux keeps its existing process-group path; the Windows-only
tree test is explicitly platform-scoped. Strong Managed/World constraints and
the complete project release gates remain separate requirements.
