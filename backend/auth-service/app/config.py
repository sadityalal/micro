from shared.database.config_service import db_config_service


class Settings:
    def __init__(self, tenant_id: int = 1):
        self.tenant_id = tenant_id

    @property
    def DATABASE_URL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            return db_config_service.get_database_url(db_session, self.tenant_id)
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def REDIS_URL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            return db_config_service.get_redis_url(db_session, self.tenant_id)
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def AUTH_SERVICE_HOST(self) -> str:
        return "0.0.0.0"

    @property
    def AUTH_SERVICE_PORT(self) -> int:
        return 8000

    @property
    def CORS_ORIGINS(self) -> list:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["security"]["cors_origins"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def RATE_LIMIT_REQUESTS_PER_MINUTE(self) -> int:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["rate_limit"]["requests_per_minute"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def LOG_LEVEL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["logging"]["log_level"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def JWT_SECRET_KEY(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["security"]["jwt_secret_key"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def JWT_ALGORITHM(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["security"]["jwt_algorithm"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["security"]["access_token_expiry_minutes"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["security"]["refresh_token_expiry_days"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass


settings = Settings()