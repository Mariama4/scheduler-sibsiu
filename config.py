def get_environment():
    from os import getenv
    from dotenv import load_dotenv

    load_dotenv()

    ENV_TYPE: str = getenv("ENV_TYPE")

    if ENV_TYPE == "PROD":
        ENV_TOKEN = "BOT_TOKEN"
        ENV_MONGODB_HOST = "MONGODB_HOST"
        ENV_MONGODB_PORT = "MONGODB_PORT"
        ENV_MONGODB_DATABASE = "MONGODB_DATABASE"
        ENV_MONGODB_USERNAME = "MONGODB_USERNAME"
        ENV_MONGODB_PASSWORD = "MONGODB_PASSWORD"
    elif ENV_TYPE == "DEV":
        ENV_TOKEN = "DEV_BOT_TOKEN"
        ENV_MONGODB_HOST = "DEV_MONGODB_HOST"
        ENV_MONGODB_PORT = "DEV_MONGODB_PORT"
        ENV_MONGODB_DATABASE = "DEV_MONGODB_DATABASE"
        ENV_MONGODB_USERNAME = "DEV_MONGODB_USERNAME"
        ENV_MONGODB_PASSWORD = "DEV_MONGODB_PASSWORD"
    else:
        raise "Неверная конфигурация среды"

    TOKEN: str = getenv(ENV_TOKEN)

    if TOKEN is None:
        raise f"{ENV_TOKEN} не установлен"

    MONGODB_HOST: str = getenv(ENV_MONGODB_HOST)

    if MONGODB_HOST is None:
        raise f"{ENV_MONGODB_HOST} не установлен"

    MONGODB_PORT: str = getenv(ENV_MONGODB_PORT)

    if MONGODB_PORT is None:
        raise f"{ENV_MONGODB_PORT} не установлен"

    MONGODB_DATABASE: str = getenv(ENV_MONGODB_DATABASE)

    if MONGODB_DATABASE is None:
        raise f"{ENV_MONGODB_DATABASE} не установлен"

    MONGODB_USERNAME: str = getenv(ENV_MONGODB_USERNAME)

    if MONGODB_USERNAME is None:
        raise f"{ENV_MONGODB_USERNAME} не установлен"

    MONGODB_PASSWORD: str = getenv(ENV_MONGODB_PASSWORD)

    if MONGODB_PASSWORD is None:
        raise f"{ENV_MONGODB_PASSWORD} не установлен"

    config = {
        "BOT_TOKEN": TOKEN,
        "MONGODB_HOST": MONGODB_HOST,
        "MONGODB_PORT": MONGODB_PORT,
        "MONGODB_DATABASE": MONGODB_DATABASE,
        "MONGODB_USERNAME": MONGODB_USERNAME,
        "MONGODB_PASSWORD": MONGODB_PASSWORD,
    }

    return config


EXPIRATION_TIME_LIMIT_SECONDS = 86400
