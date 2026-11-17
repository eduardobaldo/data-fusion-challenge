from .db import mongo_client


def main():
    client = None
    try:
        client = mongo_client()
        client.admin.command("ping")
        print("Conexão com MongoDB Atlas autenticada com sucesso.")
    except Exception as exc:
        print(f"Falha na conexão/autenticação do MongoDB Atlas: {exc}")
        raise SystemExit(1) from None
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
