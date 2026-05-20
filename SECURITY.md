If you believe you have found a security vulnerability in IssueNotified, especially one involving webhook signature verification, GitHub PAT handling, or the ability to enumerate other users' tracked repos, please report it privately.

Responsible disclosure:

1. Do not post security vulnerabilities as a public GitHub issue.
2. Please use the "Private vulnerability reporting" feature by navigating to the **Security** tab of this repository, and clicking on **Report a vulnerability**. 
3. If that feature is disabled, contact the repository owner or maintainer directly using a private channel (e.g., email from their GitHub profile).

If the issue involves exposed credentials or tokens, follow these steps immediately:

- Revoke or rotate any exposed credentials immediately (Telegram bot tokens, GitHub PATs, Gemini API keys, webhook secrets).
- Do not include the secret value in your report. Provide only the type of credential and the affected service.
- If the vulnerability is in webhook HMAC or auth checks, describe the attack flow and the affected endpoint without sharing secrets.
- Work with maintainers privately to validate and fix the issue.

Remediation guidance:

- Remove secrets from the repository or working tree.
- If secrets were committed, remove them from repository history using a tool like `git-filter-repo` or BFG.
  - Example with `git-filter-repo`:
    ```bash
    git filter-repo --replace-text replacements.txt
    ```
- Rotate credentials in affected services and update deployment secrets.
- Add secret scanning and secure configuration practices to CI.

Best practices:
- Do not store secrets in the repository. Use environment variables or a secret manager.
- Limit token scopes to the minimum required (for example, `repo` + `admin:repo_hook` for GitHub PATs only when needed).
- Keep webhook secrets and bot tokens secret and rotate them immediately if exposed.

If you need help with history cleanup or private reporting, contact a maintainer directly rather than publishing details publicly.
