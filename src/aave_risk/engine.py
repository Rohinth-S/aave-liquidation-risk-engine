from dataclasses import dataclass
from typing import Dict
@dataclass
class Position:
    id:str; collateral:float; collateral_price:float; debt:float; liquidation_threshold:float=0.8; bonus:float=0.05
    def health_factor(self): return self.collateral*self.collateral_price*self.liquidation_threshold/self.debt

def shock(p:Position, price_factor:float, gas_usd:float=12) -> dict:
    price=p.collateral_price*price_factor; hf=p.collateral*price*p.liquidation_threshold/p.debt
    liquidatable=hf<1
    repay=min(p.debt*0.5,p.collateral*price*p.liquidation_threshold) if liquidatable else 0
    seized=repay*(1+p.bonus)/price if liquidatable else 0
    return {"id":p.id,"price":price,"health_factor":hf,"liquidatable":liquidatable,"repay":repay,"seized_collateral":seized,"gas_usd":gas_usd,"bad_debt":max(0,p.debt-repay) if liquidatable else 0}

def replay(positions, factors=(-0.95,-0.8,-0.6,-0.4,-0.2,0.0)):
    return [shock(p,1+f) for p in positions for f in factors]

def alert(row):
    return "critical" if row["health_factor"]<0.95 else "watch" if row["health_factor"]<1.1 else "ok"
