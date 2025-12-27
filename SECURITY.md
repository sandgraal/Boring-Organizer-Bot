# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in B.O.B, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Report via GitHub Security Advisories:
   - Go to https://github.com/sandgraal/Boring-Organizer-Bot/security/advisories
   - Click "Report a vulnerability"
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

We will respond within 48 hours and work with you to understand and address the issue.

## Security Considerations

B.O.B is designed as a **local-first** application:

- All data is stored locally in SQLite
- No data is sent to external services by default
- Optional LLM support uses local models (llama.cpp)

### File System Access

B.O.B reads files from paths you specify. Be cautious when:

- Indexing directories with sensitive files
- Using the tool in shared environments
- Processing untrusted documents (especially PDFs)

### Database Security

The SQLite database (`data/bob.db`) contains:

- Document content (chunks)
- Embeddings
- File paths

Protect this file appropriately if it contains sensitive information.

### Dependencies

We regularly update dependencies to address security issues. Run:

```bash
pip install --upgrade -e ".[dev]"
```

to get the latest security patches.
