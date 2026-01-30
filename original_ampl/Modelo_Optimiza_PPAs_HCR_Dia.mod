# Conjuntos
set HORAS;         # Conjunto Periodos (h in HORAS)
set CONTRATOS;     # Conjunto contratos (c in CONTRATOS)
set PRY_RER;       # Conjunto Proyectos ReR (p in PRY_RER)

# Parámetros
param DemandaPortafolioActual{h in HORAS};
param DemandaPPA{h in HORAS, c in CONTRATOS};
param Produccion_Convencional{h in HORAS};
param Produccion_RER{h in HORAS, p in PRY_RER};
param PrecioPPA{c in CONTRATOS};
param PrecioSpot{h in HORAS};
param HedgeRate; # Tasa de cobertura diaria

# Variables
var y{c in CONTRATOS} binary;  # Variable binaria para seleccionar PPAs a contratar
var CompraSpot{h in HORAS} >= 0; # Volumen de energía comprado en el mercado spot por hora

# Función objetivo: Maximizar ingresos por PPAs seleccionados menos compras en el spot
maximize Ingresos:
	sum{h in HORAS, c in CONTRATOS} PrecioPPA[c] * DemandaPPA[h,c] * y[c]
    - sum{h in HORAS} PrecioSpot[h] * CompraSpot[h];

# Restricción de compra en el spot (demanda supera oferta)
subject to CompraSpotMaxima{h in HORAS}:
    CompraSpot[h] >= DemandaPortafolioActual[h] + sum{c in CONTRATOS} DemandaPPA[h,c]  * y[c]
    - Produccion_Convencional[h] - sum{p in PRY_RER} Produccion_RER[h,p];

# Restricción de balance oferta y demanda
subject to BalanceOfertaDemanda{h in HORAS}:
    DemandaPortafolioActual[h] + sum{c in CONTRATOS} DemandaPPA[h,c] * y[c] 
    <= Produccion_Convencional[h] + sum{p in PRY_RER} Produccion_RER[h,p] + CompraSpot[h];

# Restricción de cobertura diaria
subject to RestriccionCoberturaDiaria:
	(sum{h in HORAS} (DemandaPortafolioActual[h] + sum{c in CONTRATOS} DemandaPPA[h,c] * y[c]))
	/(sum{h in HORAS} (Produccion_Convencional[h] + sum{p in PRY_RER} Produccion_RER[h,p]))<= HedgeRate;

# Restricción de seleccion de PPA
subject to SeleccionContrato:
    sum{c in CONTRATOS} y[c] >= 0 and sum{c in CONTRATOS} y[c] <= 3;


