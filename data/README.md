# Demo seed data (issue #3)

Casos procesados listos para cargar en la demo, derivados de datasets públicos
de la Ciudad de Buenos Aires. La elección de fuentes viene de la investigación
de datasets del demo; ver la sección "Limitaciones" para qué representan (y qué
no representan) estos datos.

## Archivos

| Archivo | Rol | Zonas | Sitios | K | Radio |
| --- | --- | --- | --- | --- | --- |
| `cases/caba-comuna4.json` | caso compacto de comparación | 252 radios censales | 8 | 3 | 1.8 km |
| `cases/caba.json` | caso grande | 3,552 radios censales | 8 | 3 | 3.0 km |

- `caba-comuna4` cubre la Comuna 4 (La Boca / Barracas / Parque Patricios /
  Nueva Pompeya, ~218k hab.). La comuna tiene 11 instituciones de emergencia
  reales (4 hospitales + 7 cuarteles de bomberos); el caso toma las **8 que
  maximizan la brecha greedy-vs-óptimo** a este radio (regla determinista en
  `tools/build_cases.py`, los 3 omitidos quedan nombrados en `meta`). Con
  `K=3` y `r=1.8 km` el greedy cubre ~81.0% y el óptimo exacto ~85.1%: hay
  una brecha real que comparar entre métodos.
- `caba` cubre la ciudad completa (~2.89M hab. a resolución de radio censal).
  Los 8 sitios se eligen de los ~30 hospitales de agudos/niños por k-centro
  (maximizar dispersión geográfica), para mantener el formato 8-sitios/3-qubits
  del prototipo. Sirve para mostrar escala; con `K=3`, `r=3 km` la cobertura
  máxima posible es ~58% — una ciudad no se cubre con 3 ambulancias.

## Contrato del caso

```json
{
  "meta": { "...procedencia, CRS, licencias, notas de resolución..." },
  "radius_km": 1.5,
  "k_default": 3,
  "zones": [{"id": "R04-01-2", "label": "La Boca", "x_km": 101.2, "y_km": 93.4, "weight": 1240}],
  "sites": [{"id": "HOSP-012", "name": "Hospital ...", "type": "hospital", "comuna": 4, "x_km": 100.9, "y_km": 94.1}]
}
```

- `x_km`, `y_km`: easting/northing proyectados a **EPSG:9498** (POSGAR 2007 /
  CABA 2019) y pasados de metros a km. Distancias = euclídeas sobre estos km,
  igual que `baseline.py` (`(dx²+dy²) ≤ r²`). Nunca usar lon/lat como km.
- `zones[].weight`: `TOTAL_POB` del radio censal, Censo Nacional **2010**
  (última publicación por radio en el portal GCBA; el Censo 2022 existe a nivel
  comuna/radio vía IDECBA pero no en este archivo). Es la demanda proxy.
- `zones[].id`: `PA1` del radio censal (prefijo `R` + comuna-sección-fracción).
- `sites[].comuna`: comuna donde cae el punto (join espacial con barrios).

## Procedencia

| Fuente | Uso | Archivo crudo | Página de dataset | Licencia |
| --- | --- | --- | --- | --- |
| Información Censal por Radio (Censo 2010, GCBA) | zonas + `weight` | `data/raw/caba_radios_censales.geojson` | <https://data.buenosaires.gob.ar/dataset/informacion-censal-por-radio> | CC-BY-2.5-AR |
| Hospitales públicos CABA | sitios `type=hospital` | `data/raw/hospitales.geojson` | <https://data.buenosaires.gob.ar/dataset/hospitales> | CC-BY-2.5-AR |
| Cuarteles y destacamentos de Bomberos | sitios `type=bomberos` | `data/raw/cuarteles_destacamentos_bomberos.geojson` | <https://data.buenosaires.gob.ar/dataset/cuarteles-destacamentos-bomberos> | CC-BY-2.5-AR |
| Barrios (límites) | join espacial para `label`/`comuna` | `data/raw/barrios.geojson` | <https://data.buenosaires.gob.ar/dataset/barrios> | CC-BY-2.5-AR |

Atribución requerida por licencia: "Fuente: GCBA Datos Abiertos / INDEC,
Censo Nacional 2010". `data/raw/` no se commitea: se regenera con el builder.

## Regenerar

```bash
python tools/build_cases.py           # descarga fuentes (cachea en data/raw/) y reescribe data/cases/
python tools/build_cases.py --force   # fuerza re-descarga
python tools/validate_cases.py        # chequea contrato + sanity de cobertura
```

Solo stdlib de Python; sin dependencias. El builder es determinista salvo
`meta.generated_at_utc` (y el orden de desempate en la curaduría k-centro del
caso grande, que no afecta la cobertura).

## Limitaciones (honestas)

- **La población no es demanda de emergencias**: proxy estándar en literatura de
  localización de ambulancias. GCBA no publica un feed georreferenciado de
  llamadas al 107/SAME; si aparece, `weight` puede recargarse sin tocar el resto.
- **Centroides de radios**: la demanda se concentra en el centroide de cada
  radio (~200 m de lado en promedio); a r=1.5–3 km el error de borde es chico.
- **Distancia euclídea, no tiempo de viaje en calle**: el contrato del proyecto
  (ver `baseline.py`/`Idea.pdf`). Una iteración posterior puede reemplazar el
  radio por una matriz OSRM de tiempos reales.
- **Bomberos como sitios candidatos**: son cuarteles reales con personal y
  vehículos de respuesta (los Bomberos de CABA sí responden emergencias
  médicas); hospitales se listan como análogos a bases de ambulancia del SAME.
  Las 14 bases extrahospitalarias reales del SAME existen pero no están
  georreferenciadas en datos abiertos (solo una lista HTML de direcciones);
  geocodificarlas es follow-up natural para un modo "vs. ubicación actual".
