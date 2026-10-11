import os

# Run Qt without a display (CI, terminals). Must be set before PyQt6 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from carteis.data.database import connect  # noqa: E402
from carteis.data.migrations import migrate  # noqa: E402

PROVINCES = [(1, "Pontevedra"), (2, "A Coruña"), (3, "Navarra"), (4, "Zaragoza")]
MUNICIPALITIES = [
    (1, 1, "Vigo"),
    (2, 1, "Cangas"),
    (3, 2, "Ferrol"),
    (4, 3, "Castejón"),  # the same name exists in two provinces
    (5, 4, "Castejón"),
]


@pytest.fixture
def conn():
    conn = connect(":memory:")
    migrate(conn)
    conn.executemany("INSERT INTO provinces (id, name) VALUES (?, ?)", PROVINCES)
    conn.executemany(
        "INSERT INTO municipalities (id, province_id, name) VALUES (?, ?, ?)", MUNICIPALITIES
    )
    yield conn
    conn.close()
