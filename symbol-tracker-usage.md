# SymbolTracker

`SymbolTracker` maintains a mapping between **stock symbols** and **ISINs**, while also keeping a **history of symbol changes over time** for each ISIN.

It supports:

- Tracking which ISIN a symbol belongs to.
- Tracking the sequence of symbols used by an ISIN over time.
- Updating the active symbol history as new dates arrive.
- Looking up the latest symbol for an ISIN or symbol.
- Retrieving the full symbol history for an ISIN or symbol.
- Saving/loading the data to/from JSON.

---

## Internal Data Structure

```python
{
    "sym2isin": {
        "RELIANCE": "INE002A01018"
    },
    "isin2hist": {
        "INE002A01018": [
            {
                "symbol": "RELIANCE",
                "from_date": ...,
                "to_date": ...,
                "action": None
            }
        ]
    }
}
```

### `sym2isin`

Fast lookup:

```text
symbol -> ISIN
```

### `isin2hist`

History of all symbols used by an ISIN:

```text
ISIN -> [
    SymbolHistory,
    SymbolHistory,
    ...
]
```

---

## Typical Usage

### Create a new tracker

```python
tracker = SymbolTracker()
```

### Add/update a symbol

```python
tracker.update(
    symbol="RELIANCE",
    isin="INE002A01018",
    dt=date(2025, 1, 1)
)
```

Creates:

```python
RELIANCE -> INE002A01018

History:
[
    {
        "symbol": "RELIANCE",
        "from_date": 2025-01-01,
        "to_date": 2025-01-01
    }
]
```

---

### Update same symbol on a later date

```python
tracker.update(
    symbol="RELIANCE",
    isin="INE002A01018",
    dt=date(2025, 1, 2)
)
```

Instead of creating a new entry, it extends:

```python
{
    "symbol": "RELIANCE",
    "from_date": 2025-01-01,
    "to_date": 2025-01-02
}
```

---

### Symbol change for the same ISIN

```python
tracker.update(
    symbol="NEWNAME",
    isin="INE002A01018",
    dt=date(2025, 5, 1)
)
```

Creates a new history entry:

```python
[
    {
        "symbol": "RELIANCE",
        "from_date": ...,
        "to_date": ...
    },
    {
        "symbol": "NEWNAME",
        "from_date": 2025-05-01,
        "to_date": 2025-05-01
    }
]
```

and adds:

```python
sym2isin["NEWNAME"] = "INE002A01018"
```

---

## Lookup APIs

### Latest symbol by ISIN

```python
tracker.get_last_symbol(
    "INE002A01018",
    by="isin"
)
```

Returns:

```python
"NEWNAME"
```

---

### Latest symbol by old symbol

```python
tracker.get_last_symbol(
    "RELIANCE",
    by="symbol"
)
```

Returns:

```python
"NEWNAME"
```

because both symbols map to the same ISIN.

---

### Get complete history

```python
tracker.get_history(
    "INE002A01018",
    by="isin"
)
```

or

```python
tracker.get_history(
    "RELIANCE",
    by="symbol"
)
```

Returns the full symbol timeline for that security.

---

## Persistence

### Save

```python
json_text = tracker.to_json()
```

Dates are converted to ISO strings:

```json
{
  "from_date": "2025-01-01",
  "to_date": "2025-01-02"
}
```

### Load

```python
tracker = SymbolTracker(
    Path("symbols.json")
)
```
