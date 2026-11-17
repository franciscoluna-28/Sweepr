# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Instead, report it
privately via GitHub's [Security Advisories](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
("Report a vulnerability" under the repository's **Security** tab).

Include a description, reproduction steps, and the affected version. We aim to
acknowledge reports within a few days.

## Scope and threat model

Sweepr is designed for one user on a trusted machine, with an optional self-hosted
deployment for a trusted network.

- **Local use (default).** The server listens on `127.0.0.1` on a random or
  chosen port. Each launch generates an access token that the browser receives in
  the URL fragment (never sent to the server). The token lives in memory only;
  it is not written to disk and dies with the process. Every `/api` request
  except the health check must present the token. Requests with a foreign `Host`
  header are refused, which blocks DNS-rebinding attacks from web pages.
- **Self-hosting (Docker).** The container listens on all interfaces inside
  Docker, and the compose file publishes the port on `127.0.0.1` by default. It
  generates a token at startup and prints the link in its logs. Set
  `SWEEPR_TOKEN` to a long random value to keep the same token across restarts.
  Do not expose the port to an untrusted network without TLS and access control
  in front of it.
- **Engine downloads.** Each downloaded file is fetched over HTTPS and must match
  a SHA-256 checksum pinned in `sweepr_app/assets_manifest.json`. This covers both
  a published Sweepr archive and the pinned upstream `deep-filter`/ffmpeg
  components. Archives are extracted with path-traversal checks. Installer
  scripts verify the pinned uv binary the same way.
- **Processing.** Inputs are validated server-side (extensions, header probes,
  sample rates, channels, size and duration caps). External programs are started
  with argument lists, never through a shell. Files are not sent anywhere; the
  only outbound request is the engine download.
- There is no user account system and no multi-user isolation. Job data is
  pruned after 7 days.

Running Sweepr as a public, multi-tenant service is out of scope and is not
supported without significant additional hardening.
