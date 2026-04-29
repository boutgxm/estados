import csv
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "Estados.txt"
LOGS_DIR = BASE_DIR / "logs"
DDB_LOG_FILE = LOGS_DIR / "dynamodb.log"


def utc_now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def log(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{utc_now_str()}] {message}"
    with DDB_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(message, flush=True)


def get_region() -> str | None:
    region = (os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "").strip()
    return region or None


def get_table_name() -> str:
    return (os.getenv("DDB_TABLE_NAME") or "clima_estados").strip()


@dataclass(frozen=True)
class EstadoRecord:
    estado: str
    temperatura: Decimal
    humedad: Decimal
    costo_alojamiento: Decimal
    costo_transporte: Decimal
    dias_promedio: Decimal
    tiempo_traslado: Decimal

    def to_item(self) -> dict[str, Any]:
        return {
            "Estado": self.estado,
            "Temperatura": self.temperatura,
            "Humedad": self.humedad,
            "Costo_Alojamiento": self.costo_alojamiento,
            "Costo_Transporte": self.costo_transporte,
            "Dias_Promedio": self.dias_promedio,
            "Tiempo_Traslado": self.tiempo_traslado,
        }


def parse_decimal(value: str) -> Decimal:
    cleaned = value.strip().replace(",", "")
    return Decimal(cleaned)


def read_estados(file_path: Path) -> list[EstadoRecord]:
    if not file_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {file_path}")

    records: list[EstadoRecord] = []
    with file_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            if not row:
                continue

            estado_raw = (row.get("Estado") or "").strip()
            if not estado_raw:
                log(f"Línea {idx}: 'Estado' vacío. Se omite.")
                continue

            try:
                records.append(
                    EstadoRecord(
                        estado=estado_raw,
                        temperatura=parse_decimal(row.get("Temperatura") or ""),
                        humedad=parse_decimal(row.get("Humedad") or ""),
                        costo_alojamiento=parse_decimal(row.get("Costo_Alojamiento") or ""),
                        costo_transporte=parse_decimal(row.get("Costo_Transporte") or ""),
                        dias_promedio=parse_decimal(row.get("Dias_Promedio") or ""),
                        tiempo_traslado=parse_decimal(row.get("Tiempo_Traslado") or ""),
                    )
                )
            except (InvalidOperation, AttributeError):
                log(f"Línea {idx}: valores numéricos inválidos para '{estado_raw}'. Se omite.")
                continue

    return records


def table_exists(client, table_name: str) -> bool:
    try:
        client.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "ResourceNotFoundException":
            return False
        raise


def create_table_if_missing(client, table_name: str) -> bool:
    if table_exists(client, table_name):
        log(f"Tabla DynamoDB ya existe: {table_name}")
        return False

    log(f"Creando tabla DynamoDB: {table_name}")
    client.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {"AttributeName": "Estado", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "Estado", "KeyType": "HASH"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    client.get_waiter("table_exists").wait(TableName=table_name)
    while True:
        status = client.describe_table(TableName=table_name)["Table"]["TableStatus"]
        if status == "ACTIVE":
            break
        time.sleep(1)
    log(f"Tabla DynamoDB lista (ACTIVE): {table_name}")
    return True


def get_item_count(client, table_name: str) -> int:
    info = client.describe_table(TableName=table_name)
    return int(info["Table"].get("ItemCount", 0))


def seed_data(resource, table_name: str, records: list[EstadoRecord]) -> None:
    table = resource.Table(table_name)
    with table.batch_writer(overwrite_by_pkeys=["Estado"]) as batch:
        for record in records:
            batch.put_item(Item=record.to_item())


def main() -> None:
    region = get_region()
    table_name = get_table_name()

    log("Inicio: preparación DynamoDB.")
    log(f"Región: {region or 'default boto3'}")
    log(f"Tabla: {table_name}")

    client = boto3.client("dynamodb", region_name=region)
    resource = boto3.resource("dynamodb", region_name=region)

    created = create_table_if_missing(client, table_name)

    must_seed = created
    if not must_seed:
        item_count = get_item_count(client, table_name)
        log(f"ItemCount actual (aprox): {item_count}")
        must_seed = item_count == 0

    if must_seed:
        log(f"Leyendo archivo de datos: {DATA_FILE}")
        records = read_estados(DATA_FILE)
        log(f"Registros válidos detectados: {len(records)}")
        seed_data(resource, table_name, records)
        log(f"Datos cargados/actualizados en DynamoDB. Total procesado: {len(records)}")
    else:
        log("Se omite la carga de datos: tabla ya contiene registros.")

    log("Fin: preparación DynamoDB.")


if __name__ == "__main__":
    main()
