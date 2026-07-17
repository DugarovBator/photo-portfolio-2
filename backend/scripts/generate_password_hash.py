from getpass import getpass

from werkzeug.security import generate_password_hash


def main() -> None:
    password = getpass("Новый пароль администратора: ")
    confirmation = getpass("Повторите пароль: ")
    if not password:
        raise SystemExit("Пароль не может быть пустым.")
    if password != confirmation:
        raise SystemExit("Пароли не совпадают.")
    if len(password) < 12:
        raise SystemExit("Используйте пароль длиной не менее 12 символов.")
    print(generate_password_hash(password, method="scrypt"))


if __name__ == "__main__":
    main()

