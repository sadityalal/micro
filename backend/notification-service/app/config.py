from shared.database.config_service import db_config_service
from shared.database.connection import initialize_databases

class Settings:
    def __init__(self, tenant_id: int = 1):
        self.tenant_id = tenant_id
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
    def RABBITMQ_URL(self) -> str:
        return "amqp://guest:guest@rabbitmq:5672/"

    @property
    def NOTIFICATION_SERVICE_HOST(self) -> str:
        return "0.0.0.0"

    @property
    def NOTIFICATION_SERVICE_PORT(self) -> int:
        return 8005

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

settings = Settings()