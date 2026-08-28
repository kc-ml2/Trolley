from enum import StrEnum


class SystemToolName(StrEnum):
    LIST_USERS = "list_users"
    CREATE_USER = "create_user"
    UPDATE_USER_ACCESS = "update_user_access"
    LIST_API_KEYS = "list_api_keys"
    CREATE_API_KEY = "create_api_key"
    LIST_TARGETS = "list_targets"
    CREATE_TARGET = "create_target"
    TEST_TARGET_CONNECTION = "test_target_connection"
    LIST_OPERATIONS = "list_operations"
    CREATE_OPERATION = "create_operation"
    UPDATE_OPERATION = "update_operation"
    DISABLE_OPERATION = "disable_operation"
    GRANT_OPERATION = "grant_operation"
    REVOKE_OPERATION = "revoke_operation"
    LIST_OPERATION_GRANTS = "list_operation_grants"
    RELOAD_TOOLS = "reload_tools"
    EXECUTE = "execute"
