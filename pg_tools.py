import os
from dotenv import load_dotenv
import psycopg2
from typing import Optional
from langchain.tools import tool
from langchain.pydantic_v1 import BaseModel, Field
# from pydantic import BaseModel

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")  

def get_conn():
    return psycopg2.connect(DATABASE_URL)

class QueryTransactionsArgs(BaseModel):
    text: Optional[str] = Field(default=None, description="String com contexto para buscar em source_text ou description (opcional).")
    type_name: Optional[str] = Field(default=None, description="Nome do tipo: INCOME | EXPENSES | TRANSFER (opcional).")
    date_local: Optional[str] = Field(default=None, description="Data local (YYYY-MM-DD) (opcional).")
    date_from_local: Optional[str] = Field(default=None, description="Data local inicial (YYYY-MM-DD) (opcional).")
    date_to_local: Optional[str] = Field(default=None, description="Data local final (YYYY-MM-DD) (opcional).")
    limit: int = Field(default=20, description="Número limite de transações a serem retornadas.")

class UpdateTransactionArgs(BaseModel):
    id: Optional[int] = Field(
        default=None,
        description="ID da transaÃ§Ã£o a atualizar. Se ausente, serÃ¡ feita uma busca por (match_text + date_local)."
    )
    match_text: Optional[str] = Field(
        default=None,
        description="Texto para localizar transaÃ§Ã£o quando id nÃ£o for informado (busca em source_text/description)."
    )
    date_local: Optional[str] = Field(
        default=None,
        description="Data local (YYYY-MM-DD) em America/Sao_Paulo; usado em conjunto com match_text quando id ausente."
    )
    amount: Optional[float] = Field(default=None, description="Novo valor.")
    type_id: Optional[int] = Field(default=None, description="Novo type_id (1/2/3).")
    type_name: Optional[str] = Field(default=None, description="Novo type_name: INCOME | EXPENSES | TRANSFER.")
    category_id: Optional[int] = Field(default=None, description="Nova categoria (id).")
    category_name: Optional[str] = Field(default=None, description="Nova categoria (nome).")
    description: Optional[str] = Field(default=None, description="Nova descriÃ§Ã£o.")
    payment_method: Optional[str] = Field(default=None, description="Novo meio de pagamento.")
    occurred_at: Optional[str] = Field(default=None, description="Novo timestamp ISO 8601.")

class AddTransactionArgs(BaseModel):
    amount: float = Field(..., description="Valor da transação (use positivo).")
    source_text: str = Field(..., description="Texto original do usuário.")
    occurred_at: Optional[str] = Field(
        default=None,
        description="Timestamp ISO 8601; se ausente, usa NOW() no banco."
    )
    type_id: Optional[int] = Field(default=None, description="ID em transaction_types (1=INCOME, 2=EXPENSES, 3=TRANSFER).")
    type_name: Optional[str] = Field(default=None, description="Nome do tipo: INCOME | EXPENSES | TRANSFER.")
    category_id: Optional[int] = Field(default=None, description="FK de categories (opcional).")
    category_name: Optional[str] = Field(default=None, description="Nome da categoria: moradia | comida | presente | saúde | contas | férias | outros | transporte | lazer | estudo | besteira | investimento.")
    description: Optional[str] = Field(default=None, description="Descrição (opcional).")
    payment_method: Optional[str] = Field(default=None, description="Forma de pagamento (opcional).")

TYPE_ALIASES = {
    "INCOME": "INCOME", "ENTRADA": "INCOME", "RECEITA": "INCOME", "SALÁRIO": "INCOME", "EXPENSE": "EXPENSES", "EXPENSES": "EXPENSES", "DEPESA": "EXPENSES", "GASTO": "EXPENSES", "TRANSFER": "TRANSFER", "TRANSFERÊNCIA": "TRANSFER", "TRANSFERENCIA": "TRANSFER"
}

def _resolve_type_id(cur, type_id: Optional[int], type_name: Optional[str]) -> Optional[int]:
    if type_name:
        t = type_name.strip().upper()
        if t in TYPE_ALIASES:
            t = TYPE_ALIASES[t]
        cur.execute("SELECT id FROM transaction_types WHERE UPPER(type)=%s LIMIT 1;", (t,))
        row = cur.fetchone()
        return row[0] if row else None
    if type_id:
        return int(type_id)
    return 2

def _resolve_category_id(cur, category_name: Optional[str]) -> Optional[int]:
    t = category_name.strip().lower()
    cur.execute("SELECT id FROM categories WHERE LOWER(name)=%s LIMIT 1;", (t,))
    row = cur.fetchone()
    return row[0] if row else None

# Tool: add_transaction
@tool("add_transaction", args_schema=AddTransactionArgs)
def add_transaction(
    amount: float,
    source_text: str,
    occurred_at: Optional[str] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> dict:
    """Insere uma transação financeira no banco de dados Postgres.""" # docstring obrigatório da @tools do langchain (estranho, mas legal né?)
    conn = get_conn()
    cur = conn.cursor()
    try:
        resolved_type_id = _resolve_type_id(cur, type_id, type_name)
        if not resolved_type_id:
            return {"status": "error", "message": "Tipo inválido (use type_id ou type_name: INCOME/EXPENSES/TRANSFER)."}
       
        if not category_id :
            category_id = _resolve_category_id(cur, category_name) if not category_id else category_name
 
        if occurred_at:
            cur.execute(
                """
                INSERT INTO transactions
                    (amount, "type", category_id, description, payment_method, occurred_at, source_text)
                VALUES
                    (%s, %s, %s, %s, %s, %s::timestamptz, %s)
                RETURNING id, occurred_at;
                """,
                (amount, resolved_type_id, category_id, description, payment_method, occurred_at, source_text),
            )
        else:
            cur.execute(
                """
                INSERT INTO transactions
                    (amount, "type", category_id, description, payment_method, occurred_at, source_text)
                VALUES
                    (%s, %s, %s, %s, %s, NOW(), %s)
                RETURNING id, occurred_at;
                """,
                (amount, resolved_type_id, category_id, description, payment_method, source_text),
            )

        new_id, occurred = cur.fetchone()
        conn.commit()
        return {"status": "ok", "id": new_id, "occurred_at": str(occurred)}

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

# Tool: query_transactions
@tool("query_transactions", args_schema=QueryTransactionsArgs)
def query_transactions(
    text: Optional[str] = None,
    type_name: Optional[str] = None,
    date_local: Optional[str] = None,
    date_from_local: Optional[str] = None,
    date_to_local: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """
    Consulta transações com filtros por texto (source_text/description), tipo e data locais (America/Sao_Paulo).
    Os dados devem vir na seguinte ordem:
        - Intervalo (date_from_local, date_to_local): ASC(cronológico)
        - Caso contrário: DESC (mais recentes primeiro).
    """
    conn = get_conn()
    cur = conn.cursor()

    try:
        clauses, values = [], []

        if text:
            pattern = f"%{text}%"
            clauses.append("(source_text ILIKE %s OR description ILIKE %s)")
            values.extend([pattern, pattern])

        type_id = _resolve_type_id(cur, None, type_name)
        if type_id:
            clauses.append('"type" = %s')
            values.append(type_id)

        if date_local:
            clauses.append(
                "DATE(occurred_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') = %s"
            )
            values.append(date_local)

        if date_from_local or date_to_local:
            if date_from_local and date_to_local:
                clauses.append(
                    "DATE(occurred_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') BETWEEN %s AND %s"
                )
                values.extend([date_from_local, date_to_local])
            elif date_from_local:
                clauses.append(
                    "DATE(occurred_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') >= %s"
                )
                values.append(date_from_local)
            else:
                clauses.append(
                    "DATE(occurred_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') <= %s"
                )
                values.append(date_to_local)

        where_sql = " AND ".join(clauses) if clauses else "TRUE"
        order_sql = "ASC" if (date_from_local and date_to_local) else "DESC"

        sql = f"""
            SELECT 
                id, amount, "type", category_id, description, payment_method,
                occurred_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo' AS local_time,
                source_text
            FROM transactions
            WHERE {where_sql}
            ORDER BY occurred_at {order_sql}
            LIMIT %s;
        """
        values.append(limit)

        cur.execute(sql, tuple(values))
        result = cur.fetchall()

        data = [
            {
                "id": row[0],
                "amount": float(row[1]),
                "type": row[2],
                "category_id": row[3],
                "description": row[4],
                "payment_method": row[5],
                "occurred_at_local": row[6].isoformat(),
                "source_text": row[7],
            }
            for row in result
        ]

        return {"status": "ok", "transactions": data}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    finally:
        for resource in (cur, conn):
            try:
                resource.close()
            except Exception:
                pass

# Tool: total_balance
@tool("total_balance")
def total_balance() -> dict:
    """Retorna o saldo total (INCOME - EXPENSES) das transações."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN t.type = 1 THEN t.amount ELSE 0 END), 0) AS total_income, COALESCE(SUM(CASE WHEN t.type = 2 THEN t.amount ELSE 0 END), 0) AS total_expenses
            FROM transactions t;
        """)
        row = cur.fetchone()
        total_income, total_expenses = row
        balance = total_income - total_expenses
        return {
            "status": "ok",
            "total_income": float(total_income),
            "total_expenses": float(total_expenses),
            "balance": float(balance)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

# Tool: daily_balance
@tool("daily_balance")
def daily_balance(date_local: str) -> dict:
    """Retorna o saldo (INCOME - EXPENSES) do dia local informado (YYYY-MM-DD) em America/Sao Paulo."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN t.type = 1 THEN t.amount ELSE 0 END), 0) - COALESCE(SUM(CASE WHEN t.type = 2 THEN t.amount ELSE 0 END), 0)
            FROM transactions t
            WHERE DATE(t.occurred_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') = %s;
        """, (date_local,))
        balance = cur.fetchone()

        return {
            "date": date_local,
            "balance": float(balance)
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

@tool("update_transaction", args_schema=UpdateTransactionArgs)
def update_transaction(
    id: Optional[int] = None,
    match_text: Optional[str] = None,
    date_local: Optional[str] = None,
    amount: Optional[float] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> dict:
    """
    Atualiza uma transaÃ§Ã£o existente.
    EstratÃ©gias:
      - Se 'id' for informado: atualiza diretamente por ID.
      - Caso contrÃ¡rio: localiza a transaÃ§Ã£o mais recente que combine (match_text em source_text/description)
        E (date_local em America/Sao_Paulo), entÃ£o atualiza.
    Retorna: status, rows_affected, id, e o registro atualizado.
    """
    if not any([amount, type_id, type_name, category_id, category_name, description, payment_method, occurred_at]):
        return {"status": "error", "message": "Nada para atualizar: forneÃ§a pelo menos um campo (amount, type, category, description, payment_method, occurred_at)."}

    conn = get_conn()
    cur = conn.cursor()
    try:
        # Resolve target_id
        target_id = id
        if target_id is None:
            if not match_text or not date_local:
                return {"status": "error", "message": "Sem 'id': informe match_text E date_local para localizar o registro."}

            # Buscar o mais recente no dia local informado que combine o texto
            cur.execute(
                f"""
                SELECT t.id
                FROM transactions t
                WHERE (t.source_text ILIKE %s OR t.description ILIKE %s)
                  AND {_local_date_filter_sql("t.occurred_at")}
                ORDER BY t.occurred_at DESC
                LIMIT 1;
                """,
                (f"%{match_text}%", f"%{match_text}%", date_local)
            )
            row = cur.fetchone()
            if not row:
                return {"status": "error", "message": "Nenhuma transaÃ§Ã£o encontrada para os filtros fornecidos."}
            target_id = row[0]

        # Resolver type_id / category_id a partir de nomes, se fornecidos
        resolved_type_id = _resolve_type_id(cur, type_id, type_name) if (type_id or type_name) else None
        resolved_category_id = category_id
        if category_name and not category_id:
            resolved_category_id = _get_category_id(cur, category_name)

        # Montar SET dinÃ¢mico
        sets = []
        params: List[object] = []
        if amount is not None:
            sets.append("amount = %s")
            params.append(amount)
        if resolved_type_id is not None:
            sets.append("type = %s")
            params.append(resolved_type_id)
        if resolved_category_id is not None:
            sets.append("category_id = %s")
            params.append(resolved_category_id)
        if description is not None:
            sets.append("description = %s")
            params.append(description)
        if payment_method is not None:
            sets.append("payment_method = %s")
            params.append(payment_method)
        if occurred_at is not None:
            sets.append("occurred_at = %s::timestamptz")
            params.append(occurred_at)

        if not sets:
            return {"status": "error", "message": "Nenhum campo vÃ¡lido para atualizar."}

        params.append(target_id)

        cur.execute(
            f"UPDATE transactions SET {', '.join(sets)} WHERE id = %s;",
            params
        )
        rows_affected = cur.rowcount
        conn.commit()

        # Retornar o registro atualizado
        cur.execute(
            """
            SELECT
              t.id, t.occurred_at, t.amount, tt.type AS type_name,
              c.name AS category_name, t.description, t.payment_method, t.source_text
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.id = %s;
            """,
            (target_id,)
        )
        r = cur.fetchone()
        updated = None
        if r:
            updated = {
                "id": r[0],
                "occurred_at": str(r[1]),
                "amount": float(r[2]),
                "type": r[3],
                "category": r[4],
                "description": r[5],
                "payment_method": r[6],
                "source_text": r[7],
            }

        return {
            "status": "ok",
            "rows_affected": rows_affected,
            "id": target_id,
            "updated": updated
        }

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

# Exporta a lista de tools
TOOLS = [add_transaction, query_transactions, total_balance, daily_balance]