from shared.database.config_service import db_config_service
from shared.database.connection import initialize_databases

class Settings:
    def __init__(self, tenant_id: int = 1):
        self.tenant_id = tenant_id
        # Initialize database before any property access
        initialize_databases()

    def _get_db_session(self):
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        return db_session, db_gen

    @property
    def DATABASE_URL(self) -> str:
        db_session, db_gen = self._get_db_session()
        try:
            return db_config_service.get_database_url(db_session, self.tenant_id)
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def REDIS_URL(self) -> str:
        db_session, db_gen = self._get_db_session()
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
        db_session, db_gen = self._get_db_session()
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
        db_session, db_gen = self._get_db_session()
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
        db_session, db_gen = self._get_db_session()
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
        db_session, db_gen = self._get_db_session()
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
        db_session, db_gen = self._get_db_session()
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
        db_session, db_gen = self._get_db_session()
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
        db_session, db_gen = self._get_db_session()
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["security"]["refresh_token_expiry_days"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

settings = Settings()