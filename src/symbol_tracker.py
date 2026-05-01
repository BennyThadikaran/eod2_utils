from typing import List, Dict, Optional, TypedDict, Literal, cast
from datetime import date
from pathlib import Path
import json


class SymbolHistory(TypedDict):
    symbol: str
    from_date: date
    to_date: date
    action: Optional[str]


class SymbolISINMap(TypedDict):
    sym2isin: Dict[str, str]
    isin2hist: Dict[str, List[SymbolHistory]]


class SymbolTracker:
    def __init__(self, data_file: Optional[Path] = None) -> None:
        if data_file is None:
            self.data = SymbolISINMap(sym2isin={}, isin2hist={})
        else:
            self.data = self.from_json(data_file)

    def update(self, symbol: str, isin: str, dt: date):
        if isin in self.data["isin2hist"]:
            if symbol in self.data["sym2isin"]:
                if self.data["sym2isin"][symbol] == isin:
                    last = self.data["isin2hist"][isin][-1]

                    if last["symbol"] == symbol:
                        last["to_date"] = dt
                    else:
                        raise ValueError(
                            f"Expected last entry for {isin} to be {symbol}: got {last['symbol']}"
                        )
                else:
                    raise ValueError(
                        f"Expected {self.data['sym2isin'][symbol]} for {symbol}: got {isin}"
                    )

            else:
                self.data["sym2isin"][symbol] = isin
                self.data["isin2hist"][isin].append(
                    SymbolHistory(
                        symbol=symbol,
                        from_date=dt,
                        to_date=dt,
                        action=None,
                    )
                )
        else:
            self.data["isin2hist"][isin] = [
                SymbolHistory(symbol=symbol, from_date=dt, to_date=dt, action=None)
            ]
            self.data["sym2isin"][symbol] = isin

    def get_last_symbol(self, key: str, by: Literal["isin", "symbol"]) -> Optional[str]:
        if by == "isin":
            result = self.data["isin2hist"].get(key)
            return None if not result else result[-1]["symbol"]

        isin = self.data["sym2isin"].get(key)

        if isin is None:
            return None

        result = self.data["isin2hist"].get(isin)

        return None if not result else result[-1]["symbol"]

    def get_history(
        self,
        key: str,
        by: Literal["isin", "symbol"],
    ) -> Optional[List[SymbolHistory]]:
        if by == "isin":
            return self.data["isin2hist"].get(key)

        isin = self.data["sym2isin"].get(key)

        if isin is None:
            return None
        return self.data["isin2hist"].get(isin)

    def to_json(self) -> str:
        result = dict(
            sym2isin=self.data["sym2isin"],
            isin2hist={
                isin: [
                    {
                        **entry,
                        "from_date": entry["from_date"].isoformat(),
                        "to_date": entry["to_date"].isoformat(),
                    }
                    for entry in hist
                ]
                for isin, hist in self.data["isin2hist"].items()
            },
        )

        return json.dumps(result, indent=2)

    @staticmethod
    def from_json(file: Path) -> SymbolISINMap:
        result = json.loads(file.read_text())

        return cast(
            SymbolISINMap,
            dict(
                sym2isin=result["sym2isin"],
                isin2hist={
                    isin: [
                        {
                            **entry,
                            "from_date": date.fromisoformat(entry["from_date"]),
                            "to_date": date.fromisoformat(entry["to_date"]),
                        }
                        for entry in hist
                    ]
                    for isin, hist in result["isin2hist"].items()
                },
            ),
        )
