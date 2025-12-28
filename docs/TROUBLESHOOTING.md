# Troubleshooting Guide

This guide helps you diagnose and fix common issues with B.O.B.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Database Issues](#database-issues)
- [Indexing Problems](#indexing-problems)
- [Search and Retrieval Issues](#search-and-retrieval-issues)
- [Performance Problems](#performance-problems)
- [Permission Errors](#permission-errors)
- [API Server Issues](#api-server-issues)
- [Vector Search Issues](#vector-search-issues)

---

## Installation Issues

### `bob` command not found

**Symptoms:** Running `bob` results in "command not found"

**Solutions:**

1. Ensure your virtual environment is activated:
   ```bash
   source .venv/bin/activate
   ```

2. Install B.O.B in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

3. If still not found, use the full path:
   ```bash
   .venv/bin/bob --version
   # or
   python -m bob.cli.main --version
   ```

### Missing dependencies

**Symptoms:** `ModuleNotFoundError` or `ImportError` when running commands

**Solutions:**

1. Reinstall all dependencies:
   ```bash
   pip install --upgrade -e ".[dev]"
   ```

2. For specific missing modules:
   - `yaml`: Install with `pip install pyyaml`
   - `sentence_transformers`: Install with `pip install sentence-transformers`
   - `sqlite_vec`: Install with `pip install sqlite-vec`

### sqlite-vec extension not loading

**Symptoms:** Warning message "sqlite-vec not available, using fallback vector search"

**Impact:** Vector search will be slower but still functional

**Solutions:**

1. Install sqlite-vec:
   ```bash
   pip install sqlite-vec
   ```

2. Verify installation:
   ```bash
   python -c "import sqlite_vec; print('sqlite-vec installed')"
   ```

3. Reinitialize the database:
   ```bash
   bob init
   ```

**Note:** The fallback numpy-based vector search works fine for small to medium datasets.

---

## Database Issues

### Database is locked

**Symptoms:** `database is locked` or `OperationalError: database is locked`

**Causes:**
- Another B.O.B process is running
- Previous process crashed without releasing the lock
- Database is on a network drive without proper locking support

**Solutions:**

1. Check for running processes:
   ```bash
   ps aux | grep bob
   ```

2. Stop the server if running:
   ```bash
   # Find the process and kill it
   pkill -f "bob serve"
   ```

3. If the lock persists, close WAL files:
   ```bash
   # Remove WAL files (safe if no processes are running)
   rm data/bob.db-wal data/bob.db-shm
   ```

4. As a last resort, restart your system

### Database corruption

**Symptoms:**
- `sqlite3.DatabaseError: database disk image is malformed`
- Unexpected errors when running queries
- Missing data

**Solutions:**

1. Check database integrity:
   ```bash
   sqlite3 data/bob.db "PRAGMA integrity_check;"
   ```

2. If you have a backup, restore it:
   ```bash
   bob restore backups/bob-YYYY-MM-DD.db
   ```

3. Try to recover:
   ```bash
   # Dump and recreate database
   sqlite3 data/bob.db ".dump" | sqlite3 data/bob_recovered.db
   mv data/bob.db data/bob_corrupted.db
   mv data/bob_recovered.db data/bob.db
   bob init  # Reinitialize
   ```

4. If all else fails, reinitialize and re-index:
   ```bash
   mv data/bob.db data/bob_old.db
   bob init
   bob index --watchlist
   ```

### Out of disk space

**Symptoms:** `database or disk is full`

**Solutions:**

1. Check disk space:
   ```bash
   df -h
   ```

2. Clean up old backups:
   ```bash
   rm backups/*.pre-restore
   ```

3. Vacuum the database to reclaim space:
   ```bash
   sqlite3 data/bob.db "VACUUM;"
   ```

4. Consider moving the database to a larger drive:
   ```yaml
   # In bob.yaml
   database:
     path: /path/to/larger/drive/bob.db
   ```

---

## Indexing Problems

### Files not being indexed

**Symptoms:** `bob index` completes but files don't appear in search results

**Causes:**
- Files are in ignored directories
- Files exceed max size limit
- File parsing failed

**Solutions:**

1. Check indexing status:
   ```bash
   bob status
   ```

2. Try indexing with verbose output:
   ```bash
   bob -v index /path/to/files --project test
   ```

3. Check if files are in ignored directories:
   ```yaml
   # In bob.yaml, check paths.ignore
   paths:
     ignore:
       - node_modules
       - .git
       - __pycache__
   ```

4. Check file size limits:
   ```yaml
   # In bob.yaml
   paths:
     max_file_size_mb: 50  # Increase if needed
   ```

5. Check ingestion errors via API:
   ```bash
   curl http://localhost:8080/health/fix-queue
   ```

### Parsing errors for specific file types

**Symptoms:** Errors like "Failed to parse PDF" or "Could not read DOCX"

**Solutions:**

1. Verify file is not corrupted:
   ```bash
   file /path/to/problem-file.pdf
   ```

2. Install additional dependencies:
   - PDF issues: `pip install --upgrade pypdf`
   - Word issues: `pip install --upgrade python-docx`
   - Excel issues: `pip install --upgrade openpyxl`

3. Try opening the file in its native application to verify it's valid

4. Check file permissions:
   ```bash
   ls -l /path/to/problem-file.pdf
   ```

### Git repository indexing fails

**Symptoms:** `bob index https://github.com/user/repo` fails

**Solutions:**

1. Verify git is installed:
   ```bash
   git --version
   ```

2. Check network connectivity:
   ```bash
   ping github.com
   ```

3. For private repos, clone manually first:
   ```bash
   git clone https://github.com/user/repo /tmp/repo
   bob index /tmp/repo --project repo
   ```

4. Check git credentials:
   ```bash
   git config --global user.name
   git config --global user.email
   ```

---

## Search and Retrieval Issues

### "Not found in sources" for content you know exists

**Symptoms:** B.O.B returns "Not found in sources" but you know the content exists

**Causes:**
- Content not indexed
- Query doesn't match indexed content semantically
- Filters excluding relevant results

**Solutions:**

1. Verify content is indexed:
   ```bash
   bob status --project your-project
   ```

2. Try a more specific search:
   ```bash
   bob search "exact phrase from document" --project your-project
   ```

3. Remove filters to broaden search:
   ```bash
   bob ask "your question" --top-k 20
   ```

4. Re-index the content:
   ```bash
   bob index /path/to/files --project your-project
   ```

5. Enable hybrid search for better recall:
   ```yaml
   # In bob.yaml
   search:
     hybrid_enabled: true
   ```

### Poor search results quality

**Symptoms:** Irrelevant results returned, or good results ranked low

**Solutions:**

1. Increase the number of results:
   ```bash
   bob ask "your question" --top-k 10
   ```

2. Use advanced search syntax:
   ```bash
   # Exact phrase matching
   bob ask '"exact phrase" other terms'

   # Exclude terms
   bob ask "query -unwanted -terms"

   # Filter by project
   bob ask "query project:specific-project"
   ```

3. Adjust hybrid search weights:
   ```yaml
   # In bob.yaml
   search:
     hybrid_enabled: true
     vector_weight: 0.7    # Semantic similarity
     keyword_weight: 0.3   # Keyword matching
   ```

4. Enable recency boosting:
   ```yaml
   # In bob.yaml
   search:
     recency_boost_enabled: true
     recency_half_life_days: 90
   ```

---

## Performance Problems

### Slow search responses

**Symptoms:** Queries take more than a few seconds

**Causes:**
- Large database without sqlite-vec
- Too many indexed documents
- Inefficient queries

**Solutions:**

1. Install sqlite-vec for faster vector search:
   ```bash
   pip install sqlite-vec
   bob init  # Reinitialize to enable
   ```

2. Check database size:
   ```bash
   bob status
   ls -lh data/bob.db
   ```

3. Optimize the database:
   ```bash
   sqlite3 data/bob.db "ANALYZE; VACUUM;"
   ```

4. Reduce top-k if searching many results:
   ```bash
   bob ask "query" --top-k 5  # Instead of 20
   ```

5. Filter by project to narrow search scope:
   ```bash
   bob ask "query" --project specific-project
   ```

### Slow indexing

**Symptoms:** Indexing takes very long

**Solutions:**

1. Use watchlist for batch indexing:
   ```bash
   bob watchlist add /path/to/files --project project-name
   bob index --watchlist
   ```

2. Index fewer files at once:
   ```bash
   # Instead of entire directory
   bob index /path/to/files --project project

   # Do subdirectories separately
   bob index /path/to/files/subdir1 --project project
   bob index /path/to/files/subdir2 --project project
   ```

3. Adjust batch size for embeddings:
   ```yaml
   # In bob.yaml
   embedding:
     batch_size: 64  # Increase for faster processing
   ```

4. Check system resources:
   ```bash
   top  # Monitor CPU and memory usage
   ```

### High memory usage

**Symptoms:** B.O.B uses excessive RAM

**Solutions:**

1. Reduce embedding batch size:
   ```yaml
   # In bob.yaml
   embedding:
     batch_size: 16  # Smaller batches
   ```

2. Use CPU instead of GPU (if applicable):
   ```yaml
   # In bob.yaml
   embedding:
     device: cpu
   ```

3. Close unused database connections:
   ```bash
   # Restart the server
   pkill -f "bob serve"
   bob serve
   ```

---

## Permission Errors

### PERMISSION_DENIED errors

**Symptoms:** API returns 403 with `PERMISSION_DENIED` error

**Causes:**
- Scope level too low for the requested operation
- Target path not in allowed_vault_paths
- Connector disabled

**Solutions:**

1. Check current permission settings:
   ```bash
   # Via API
   curl http://localhost:8080/settings
   ```

2. Raise permission scope in config:
   ```yaml
   # In bob.yaml
   permissions:
     default_scope: 3  # Required for template writes
   ```

3. Add required paths to allowed list:
   ```yaml
   # In bob.yaml
   permissions:
     allowed_vault_paths:
       - vault/routines
       - vault/decisions
       - vault/your-custom-path
   ```

4. Enable required connectors:
   ```yaml
   # In bob.yaml
   permissions:
     enabled_connectors:
       browser_saves: true
   ```

5. Check permission denials in Fix Queue:
   ```bash
   curl http://localhost:8080/health/fix-queue
   ```

### File permission errors during indexing

**Symptoms:** "Permission denied" when reading files

**Solutions:**

1. Check file permissions:
   ```bash
   ls -l /path/to/file
   ```

2. Grant read permissions:
   ```bash
   chmod +r /path/to/file
   # or for directories
   chmod -R +r /path/to/directory
   ```

3. Run as appropriate user:
   ```bash
   # Don't run as root unless necessary
   whoami  # Check current user
   ```

---

## API Server Issues

### Server won't start

**Symptoms:** `bob serve` fails or crashes immediately

**Solutions:**

1. Check if port is already in use:
   ```bash
   lsof -i :8080
   # or
   netstat -an | grep 8080
   ```

2. Use a different port:
   ```bash
   bob serve --port 9000
   ```

3. Check for errors:
   ```bash
   bob -v serve  # Verbose output
   ```

4. Verify database is accessible:
   ```bash
   bob status
   ```

### Cannot connect to server

**Symptoms:** Browser shows "connection refused" at localhost:8080

**Solutions:**

1. Verify server is running:
   ```bash
   ps aux | grep "bob serve"
   ```

2. Check server logs for errors

3. Try binding to all interfaces:
   ```bash
   bob serve --host 0.0.0.0
   ```

4. Check firewall settings:
   ```bash
   # On Linux
   sudo ufw status
   ```

### UI not loading

**Symptoms:** Server runs but UI doesn't load in browser

**Solutions:**

1. Clear browser cache and reload

2. Check browser console for errors (F12)

3. Verify static files exist:
   ```bash
   ls -la bob/ui/
   ```

4. Try a different browser

5. Access API directly to verify it's working:
   ```bash
   curl http://localhost:8080/health
   ```

---

## Vector Search Issues

### Embeddings failing to generate

**Symptoms:** Errors mentioning `sentence-transformers` or embedding model

**Solutions:**

1. Reinstall sentence-transformers:
   ```bash
   pip install --upgrade sentence-transformers
   ```

2. Download model manually:
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer('all-MiniLM-L6-v2')
   ```

3. Check model dimension matches config:
   ```yaml
   # In bob.yaml
   embedding:
     model: all-MiniLM-L6-v2
     dimension: 384  # Must match model output
   ```

4. Use a different model:
   ```yaml
   # In bob.yaml
   embedding:
     model: paraphrase-MiniLM-L6-v2
     dimension: 384
   ```

### Vector dimension mismatch

**Symptoms:** `dimension mismatch` errors

**Causes:**
- Changed embedding model without re-indexing
- Config doesn't match model output dimension

**Solutions:**

1. Verify model dimension:
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer('all-MiniLM-L6-v2')
   print(model.get_sentence_embedding_dimension())  # Should be 384
   ```

2. Update config to match:
   ```yaml
   # In bob.yaml
   embedding:
     dimension: 384  # Match model output
   ```

3. If you changed models, you must re-index everything:
   ```bash
   mv data/bob.db data/bob_old.db
   bob init
   bob index --watchlist
   ```

---

## Getting More Help

If you're still having issues:

1. **Check the logs:**
   ```bash
   bob -v <command>  # Verbose mode
   ```

2. **Verify installation:**
   ```bash
   bob --version
   pip list | grep -E "bob|pyyaml|pydantic|sentence-transformers|sqlite-vec"
   ```

3. **Check database status:**
   ```bash
   bob status
   sqlite3 data/bob.db "PRAGMA integrity_check;"
   ```

4. **Review configuration:**
   ```bash
   cat bob.yaml
   ```

5. **Search existing issues:**
   - GitHub: https://github.com/sandgraal/Boring-Organizer-Bot/issues

6. **Report a bug:**
   - Create a new issue at https://github.com/sandgraal/Boring-Organizer-Bot/issues
   - Include:
     - B.O.B version (`bob --version`)
     - Python version (`python --version`)
     - Operating system
     - Error messages (with verbose output)
     - Steps to reproduce

7. **Security issues:**
   - See [SECURITY.md](../SECURITY.md) for responsible disclosure

---

## Preventive Maintenance

To avoid issues, follow these best practices:

### Regular backups

```bash
# Create automated backup script
mkdir -p backups
bob backup backups/bob-$(date +%Y-%m-%d).db --compress

# Keep only last 7 days of backups
find backups/ -name "*.db.gz" -mtime +7 -delete
```

### Database optimization

```bash
# Weekly maintenance
sqlite3 data/bob.db "PRAGMA optimize; VACUUM; ANALYZE;"
```

### Monitor database size

```bash
# Check growth
du -h data/bob.db
bob status  # Check document counts
```

### Keep dependencies updated

```bash
# Monthly update
pip install --upgrade -e ".[dev]"
```

### Test after updates

```bash
# Verify everything works
make test
bob status
```

---

**Last Updated:** 2025-12-27
