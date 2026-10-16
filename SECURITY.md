# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Instead, report it
privately via GitHub's [Security Advisories](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
("Report a vulnerability" under the repository's **Security** tab).

Include a description, reproduction steps, and the affected version. We aim to
acknowledge reports within a few days.

## Scope and threat model

Sweepr is designed to run **locally, on a trusted machine, for a single user**:

- It binds to `127.0.0.1` by default (`start.py`). The Docker images bind to
  `0.0.0.0` so the port can be published; do not expose that port to an
  untrusted network without adding authentication and TLS in front of it.
- There is no authentication or multi-user isolation. Uploaded files and job
  data are written under `SWEEPR_JOBS_DIR` and pruned after
  `SWEEPR_RETENTION_DAYS`.
- All input is validated server-side (extensions, header probes, sample rates,
  channels, size and duration caps). Files are never uploaded anywhere; the app
  makes no outbound network calls except the one-time DeepFilterNet model
  download.

Running Sweepr as a public, multi-tenant service is out of scope and is not
supported without significant additional hardening.
