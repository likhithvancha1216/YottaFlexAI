def po_id(n: int, year: int = 2026) -> str:
    return f"PO-{year}-{n:06d}"

def ack_id(po: str, seq: int) -> str:
    return f"ACK-{po}-{seq:02d}"

def chg_id(po: str, seq: int) -> str:
    return f"CHG-{po}-{seq:06d}"

def apr_id(chg: str, seq: int) -> str:
    return f"APR-{chg}-{seq:02d}"

def not_id(n: int, year: int = 2026) -> str:
    return f"NOT-{year}-{n:06d}"

def supplier_id(n: int) -> str:
    return f"SUP-{n:04d}"

def line_id(po: str, n: int) -> str:
    return f"{po}-L{n:02d}"

def promise_id(line: str, rev: int) -> str:
    return f"PRM-{line}-{rev:02d}"

def plan_id(line: str, version: int) -> str:
    return f"INV-{line}-{version:02d}"

def prod_id(n: int, year: int = 2026) -> str:
    return f"PRD-{year}-{n:06d}"