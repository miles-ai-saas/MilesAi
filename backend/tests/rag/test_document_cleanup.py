from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_portal.deletion.document import (
    clear_document_derived_data_async,
    clear_document_derived_data_sync,
)


@pytest.mark.asyncio
async def test_clear_document_derived_data_async_order() -> None:
    document_id = uuid4()
    chunk_id = uuid4()

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=lambda: [chunk_id]))))

    with patch("miles_portal.deletion.document.delete_by_document") as mock_wv:
        await clear_document_derived_data_async(db, document_id)

    assert db.execute.await_count == 3  # select chunk ids + delete vector_refs + delete chunks
    mock_wv.assert_called_once_with(document_id)


def test_clear_document_derived_data_sync_order() -> None:
    document_id = uuid4()
    chunk_id = uuid4()

    db = MagicMock()
    db.scalars.return_value = [chunk_id]

    with patch("miles_portal.deletion.document.delete_by_document") as mock_wv:
        clear_document_derived_data_sync(db, document_id)

    assert db.execute.call_count == 2
    mock_wv.assert_called_once_with(document_id)
