BAC-4420: Stop retrying a Chall space delete that can never succeed

delete_orphaned_space retried a 403 until its retry budget ran out:
Chall answers 403 for a space that moved to another partner, and only
404 was treated as done. Treat a space Chall won't let us delete as
gone, as a 404 already is.
