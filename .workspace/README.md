# Workspace Directory

## Purpose
This directory is used by the WriteFileTool for safe file operations performed by agents in the Nayu_AI system.

## Security Note
All agent file writes are restricted to this directory. This is enforced by the system's guardrails to prevent unauthorized file access or modification outside this workspace.

## Usage Guidance
Files created in this directory are gitignored by default (except this README). This helps prevent accidental commits of agent-generated files.

## Maintenance Instructions
Manual cleanup of files in this directory may be required periodically, especially after large experiments or when disk space is limited.

---

For more information, see the main project README and security documentation.
