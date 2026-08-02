from app.dependencies import get_rag_service


def main() -> None:
    result = get_rag_service().rebuild_vectorstore()
    print(
        "Indexed "
        f"{result['documents']} documents into {result['chunks']} chunks "
        f"across {result['cities']} cities."
    )


if __name__ == "__main__":
    main()
