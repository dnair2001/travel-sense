import logging
import sys

from app.dependencies import get_rag_service

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        result = get_rag_service().rebuild_vectorstore()
    except Exception:
        logger.exception("Vectorstore rebuild failed")
        sys.exit(1)
    print(
        "Indexed "
        f"{result['documents']} documents into {result['chunks']} chunks "
        f"across {result['cities']} cities."
    )


if __name__ == "__main__":
    main()
