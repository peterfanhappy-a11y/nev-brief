import os
from uuid import uuid4

import pytest
import psycopg

from nev_crawler.storage import insert_articles_raw, hash_content
from python.content import ArticleRaw


@pytest.fixture(scope="module")
def db():
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://nev:nev_local_dev@localhost:54322/nev_brief",
    )
    conn = psycopg.connect(url)
    yield conn
    conn.close()


@pytest.fixture
def source_id(db):
    sid = uuid4()
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO sources (id, name, type, url, authority, locale, category)
               VALUES (%s, %s, 'rss', 'http://x/feed', 5, 'zh', 'media')""",
            (str(sid), f"storage-test-{sid}"),
        )
    db.commit()
    return sid


@pytest.mark.integration
def test_insert_articles_raw_writes_and_dedupes(db, source_id):
    articles = [
        ArticleRaw(source_id=source_id, url=f"https://test.com/a/{uuid4()}", title="A"),
        ArticleRaw(source_id=source_id, url=f"https://test.com/b/{uuid4()}", title="B"),
    ]
    inserted = insert_articles_raw(db, articles)
    db.commit()
    assert inserted == 2

    # Re-insert same URLs → 0 inserts (URL UNIQUE)
    re_inserted = insert_articles_raw(db, articles)
    db.commit()
    assert re_inserted == 0


@pytest.mark.integration
def test_hash_content_is_stable():
    h1 = hash_content("hello world")
    h2 = hash_content("hello world")
    assert h1 == h2
    assert len(h1) == 16  # blake2b 8-byte digest = 16 hex chars
