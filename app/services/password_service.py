from passlib.context import CryptContext


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


class PasswordService:

    @staticmethod
    def hash_password(
        password: str,
    ) -> str:

        return pwd_context.hash(password)

    @staticmethod
    def verify_password(
        plain_password: str,
        password_hash: str,
    ) -> bool:

        return pwd_context.verify(
            plain_password,
            password_hash,
        )