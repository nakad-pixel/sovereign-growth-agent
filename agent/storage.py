"""Durable memory in a Cloudflare R2 bucket (S3 API). R2 is the source of truth when configured;
files are mirrored to memory/ locally. Without R2 env vars everything is a no-op (git remains the store)."""
import hashlib

from . import config

PREFIX = "memory/"
_synced = {}


def enabled():
    return all(config.env(k) for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"))


def _client():
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3", endpoint_url=f"https://{config.env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=config.env("R2_ACCESS_KEY_ID"), aws_secret_access_key=config.env("R2_SECRET_ACCESS_KEY"),
        region_name="auto", config=Config(retries={"max_attempts": 3}, signature_version="s3v4"))


def _md5(data):
    return hashlib.md5(data).hexdigest()


def pull(client=None):
    """Download every object under memory/ into the local memory folder. Returns file count."""
    if not enabled():
        return 0
    c, bucket, n, token = client or _client(), config.env("R2_BUCKET"), 0, None
    while True:
        kw = {"Bucket": bucket, "Prefix": PREFIX}
        if token:
            kw["ContinuationToken"] = token
        page = c.list_objects_v2(**kw)
        for obj in page.get("Contents", []):
            rel = obj["Key"][len(PREFIX):]
            if not rel or rel.startswith("/") or ".." in rel.split("/"):
                continue
            body = c.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            dest = config.MEM / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
            _synced[obj["Key"]] = _md5(body)
            n += 1
        if not page.get("IsTruncated"):
            return n
        token = page.get("NextContinuationToken")


def push(client=None):
    """Upload only files that changed since the last sync. Returns number uploaded."""
    if not enabled():
        return 0
    c, bucket, n = client or _client(), config.env("R2_BUCKET"), 0
    for path in sorted(config.MEM.rglob("*")):
        if not path.is_file() or path.suffix == ".tmp" or path.name == ".gitkeep":
            continue
        key = PREFIX + path.relative_to(config.MEM).as_posix()
        data = path.read_bytes()
        if _synced.get(key) != _md5(data):
            c.put_object(Bucket=bucket, Key=key, Body=data)
            _synced[key] = _md5(data)
            n += 1
    return n


def reset():
    _synced.clear()
