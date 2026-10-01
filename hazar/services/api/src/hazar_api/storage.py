from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol


class ObjectNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class StoredObject:
    data: bytes
    content_type: str


class ObjectStorage(Protocol):
    """Raw blob store. Receives only ciphertext; encryption happens in DocumentVault."""

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> StoredObject: ...

    async def delete(self, key: str) -> None: ...


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = StoredObject(data, content_type)

    async def get(self, key: str) -> StoredObject:
        try:
            return self.objects[key]
        except KeyError:
            raise ObjectNotFoundError(key) from None

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class S3ObjectStorage:
    """S3-compatible storage (SeaweedFS locally, see ADR 0002). boto3 is sync, so calls run in a thread."""

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> None:
        import boto3

        self._bucket = bucket
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            region_name=region,
        )

    def _ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    async def ensure_bucket(self) -> None:
        await asyncio.to_thread(self._ensure_bucket)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType="application/octet-stream",
            Metadata={"plain-content-type": content_type},
        )

    async def get(self, key: str) -> StoredObject:
        from botocore.exceptions import ClientError

        try:
            obj = await asyncio.to_thread(self._client.get_object, Bucket=self._bucket, Key=key)
        except ClientError as err:
            if err.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise ObjectNotFoundError(key) from None
            raise
        body = await asyncio.to_thread(obj["Body"].read)
        content_type = obj.get("Metadata", {}).get("plain-content-type", "application/octet-stream")
        return StoredObject(body, content_type)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)
